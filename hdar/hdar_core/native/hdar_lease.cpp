// hdar_lease.cpp — SQLite-backed lease manager with fencing tokens (pure C++).

#include "hdar_lease.h"
#include "hdar_crypto.h"
#include <sqlite3.h>
#include <sstream>
#include <random>
#include <chrono>

namespace hdar {

// ─── FencingInvalidation ───────────────────────────────────────────────

std::string FencingInvalidation::to_json() const {
    std::ostringstream ss;
    ss << "{"
       << "\"agent_id\":\"" << agent_id << "\""
       << ",\"lease_generation\":" << lease_generation
       << ",\"fencing_token\":\"" << fencing_token << "\""
       << ",\"holder_id\":\"" << holder_id << "\""
       << ",\"runtime_id\":\"" << runtime_id << "\""
       << ",\"invalidated_at\":" << invalidated_at
       << ",\"reason\":\"" << reason << "\""
       << "}";
    return ss.str();
}

FencingInvalidation FencingInvalidation::from_json(const std::string& json) {
    FencingInvalidation f;
    auto find_str = [&](const std::string& key) -> std::string {
        size_t pos = json.find("\"" + key + "\"");
        if (pos == std::string::npos) return "";
        size_t s = json.find("\"", pos + key.size() + 2) + 1;
        size_t e = json.find("\"", s);
        return json.substr(s, e - s);
    };
    auto find_int = [&](const std::string& key) -> int64_t {
        size_t pos = json.find("\"" + key + "\"");
        if (pos == std::string::npos) return 0;
        size_t s = json.find(":", pos + key.size() + 2) + 1;
        size_t e = json.find_first_of(",}", s);
        return std::stoll(json.substr(s, e - s));
    };

    f.agent_id = find_str("agent_id");
    f.lease_generation = find_int("lease_generation");
    f.fencing_token = find_str("fencing_token");
    f.holder_id = find_str("holder_id");
    f.runtime_id = find_str("runtime_id");
    f.invalidated_at = (double)find_int("invalidated_at");
    f.reason = find_str("reason");
    return f;
}

// ─── LeaseManager ──────────────────────────────────────────────────────

static double now_seconds() {
    auto now = std::chrono::system_clock::now();
    return std::chrono::duration<double>(now.time_since_epoch()).count();
}

LeaseManager::LeaseManager(const std::string& db_path) : db_path_(db_path) {
    init_db();
}

LeaseManager::~LeaseManager() {
    if (db_) sqlite3_close((sqlite3*)db_);
}

void LeaseManager::init_db() {
    int rc = sqlite3_open(db_path_.c_str(), (sqlite3**)&db_);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "FATAL: cannot open lease DB: %s\n", sqlite3_errmsg((sqlite3*)db_));
        return;
    }

    const char* sql =
        "CREATE TABLE IF NOT EXISTS leases ("
        "  agent_id TEXT PRIMARY KEY,"
        "  capsule_hash TEXT,"
        "  lease_generation INTEGER,"
        "  fencing_token TEXT,"
        "  holder_id TEXT,"
        "  runtime_id TEXT,"
        "  acquired_at REAL,"
        "  expires_at REAL,"
        "  active INTEGER"
        ");"
        "CREATE TABLE IF NOT EXISTS generation ("
        "  counter INTEGER DEFAULT 0"
        ");"
        "INSERT OR IGNORE INTO generation VALUES (0);";

    char* err = nullptr;
    rc = sqlite3_exec((sqlite3*)db_, sql, nullptr, nullptr, &err);
    if (err) { fprintf(stderr, "Lease DB init error: %s\n", err); sqlite3_free(err); }
}

std::string LeaseManager::generate_uuid() {
    std::random_device rd;
    std::uniform_int_distribution<uint32_t> dist(0, 0xFFFFFFFF);
    char buf[37];
    snprintf(buf, sizeof(buf), "%08x-%04x-%04x-%04x-%04x%08x",
             dist(rd), dist(rd) & 0xFFFF, (dist(rd) & 0x0FFF) | 0x4000,
             (dist(rd) & 0x3FFF) | 0x8000, dist(rd) & 0xFFFF, dist(rd));
    return std::string(buf);
}

std::pair<std::optional<Lease>, std::string> LeaseManager::acquire(
    const std::string& agent_id,
    const std::string& capsule_hash,
    int64_t min_generation,
    const std::string& holder_id,
    const std::string& runtime_id,
    double ttl_seconds
) {
    std::lock_guard<std::mutex> lock(mutex_);
    double now = now_seconds();

    sqlite3_stmt* stmt;
    const char* check = "SELECT lease_generation, fencing_token, active, expires_at FROM leases WHERE agent_id = ?";
    sqlite3_prepare_v2((sqlite3*)db_, check, -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);

    if (sqlite3_step(stmt) == SQLITE_ROW) {
        int active = sqlite3_column_int(stmt, 2);
        double expires = sqlite3_column_double(stmt, 3);
        if (active && now < expires) {
            sqlite3_finalize(stmt);
            return {std::nullopt, "lease already held by agent " + agent_id};
        }
    }
    sqlite3_finalize(stmt);

    sqlite3_exec((sqlite3*)db_, "UPDATE generation SET counter = counter + 1", nullptr, nullptr, nullptr);
    sqlite3_prepare_v2((sqlite3*)db_, "SELECT counter FROM generation", -1, &stmt, nullptr);
    sqlite3_step(stmt);
    int64_t new_gen = sqlite3_column_int64(stmt, 0);
    sqlite3_finalize(stmt);

    if (new_gen < min_generation) new_gen = min_generation + 1;

    std::string token = generate_uuid();
    double expires = now + ttl_seconds;

    const char* upsert =
        "INSERT OR REPLACE INTO leases "
        "(agent_id, capsule_hash, lease_generation, fencing_token, holder_id, runtime_id, acquired_at, expires_at, active) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)";
    sqlite3_prepare_v2((sqlite3*)db_, upsert, -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, capsule_hash.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 3, new_gen);
    sqlite3_bind_text(stmt, 4, token.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 5, holder_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 6, runtime_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_double(stmt, 7, now);
    sqlite3_bind_double(stmt, 8, expires);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    Lease lease;
    lease.agent_id = agent_id;
    lease.capsule_hash = capsule_hash;
    lease.lease_generation = new_gen;
    lease.fencing_token = token;
    lease.holder_id = holder_id;
    lease.runtime_id = runtime_id;
    lease.acquired_at = now;
    lease.expires_at = expires;
    lease.active = true;

    return {lease, ""};
}

std::string LeaseManager::release(const std::string& agent_id, const std::string& fencing_token) {
    std::lock_guard<std::mutex> lock(mutex_);

    sqlite3_stmt* stmt;
    const char* sql = "UPDATE leases SET active = 0 WHERE agent_id = ? AND fencing_token = ?";
    sqlite3_prepare_v2((sqlite3*)db_, sql, -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, fencing_token.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_step(stmt);
    int changes = sqlite3_changes((sqlite3*)db_);
    sqlite3_finalize(stmt);

    return changes == 0 ? "no matching active lease" : "";
}

std::string LeaseManager::force_release(const std::string& agent_id) {
    std::lock_guard<std::mutex> lock(mutex_);

    sqlite3_stmt* stmt;
    const char* sql = "UPDATE leases SET active = 0 WHERE agent_id = ? AND active = 1";
    sqlite3_prepare_v2((sqlite3*)db_, sql, -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_step(stmt);
    int changes = sqlite3_changes((sqlite3*)db_);
    sqlite3_finalize(stmt);

    return changes == 0 ? "no active lease" : "";
}

bool LeaseManager::validate_token(const std::string& agent_id, const std::string& fencing_token) {
    std::lock_guard<std::mutex> lock(mutex_);
    double now = now_seconds();

    sqlite3_stmt* stmt;
    const char* sql = "SELECT active, expires_at FROM leases WHERE agent_id = ? AND fencing_token = ?";
    sqlite3_prepare_v2((sqlite3*)db_, sql, -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, fencing_token.c_str(), -1, SQLITE_TRANSIENT);

    bool valid = false;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        int active = sqlite3_column_int(stmt, 0);
        double expires = sqlite3_column_double(stmt, 1);
        valid = (active == 1) && (now < expires);
    }
    sqlite3_finalize(stmt);
    return valid;
}

std::string LeaseManager::invalidate(const std::string& agent_id, const std::string& fencing_token) {
    return release(agent_id, fencing_token);
}

std::optional<Lease> LeaseManager::get_lease(const std::string& agent_id) {
    std::lock_guard<std::mutex> lock(mutex_);

    sqlite3_stmt* stmt;
    const char* sql = "SELECT capsule_hash, lease_generation, fencing_token, holder_id, runtime_id, acquired_at, expires_at, active FROM leases WHERE agent_id = ?";
    sqlite3_prepare_v2((sqlite3*)db_, sql, -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);

    if (sqlite3_step(stmt) == SQLITE_ROW) {
        Lease lease;
        lease.agent_id = agent_id;
        lease.capsule_hash = (const char*)sqlite3_column_text(stmt, 0);
        lease.lease_generation = sqlite3_column_int64(stmt, 1);
        lease.fencing_token = (const char*)sqlite3_column_text(stmt, 2);
        lease.holder_id = (const char*)sqlite3_column_text(stmt, 3);
        lease.runtime_id = (const char*)sqlite3_column_text(stmt, 4);
        lease.acquired_at = sqlite3_column_double(stmt, 5);
        lease.expires_at = sqlite3_column_double(stmt, 6);
        lease.active = sqlite3_column_int(stmt, 7) == 1;
        sqlite3_finalize(stmt);
        return lease;
    }
    sqlite3_finalize(stmt);
    return std::nullopt;
}

} // namespace hdar
