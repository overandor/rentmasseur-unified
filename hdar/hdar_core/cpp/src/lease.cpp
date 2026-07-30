#include "hdar/lease.hpp"
#include <sqlite3.h>
#include <filesystem>

namespace hdar {

bool Lease::is_expired() const {
    return epoch_seconds() > expires_at;
}

JsonValue Lease::to_json() const {
    JsonValue v = JsonValue::object();
    v["agent_id"] = JsonValue::string(agent_id);
    v["capsule_hash"] = JsonValue::string(capsule_hash);
    v["epoch"] = JsonValue::integer(epoch);
    v["lease_generation"] = JsonValue::integer(lease_generation);
    v["holder_id"] = JsonValue::string(holder_id);
    v["destination_runtime"] = JsonValue::string(destination_runtime);
    v["fencing_token"] = JsonValue::string(fencing_token);
    v["issued_at"] = JsonValue::number(issued_at);
    v["expires_at"] = JsonValue::number(expires_at);
    return v;
}

LeaseManager::LeaseManager(const std::string& db_path, int ttl)
    : db_path_(db_path), ttl_(ttl) {
    auto parent = std::filesystem::path(db_path).parent_path();
    if (!parent.empty())
        std::filesystem::create_directories(parent);
    init_schema();
}

void LeaseManager::init_schema() {
    sqlite3* db = nullptr;
    sqlite3_open(db_path_.c_str(), &db);
    const char* schema =
        "CREATE TABLE IF NOT EXISTS leases ("
        "  agent_id TEXT PRIMARY KEY,"
        "  capsule_hash TEXT NOT NULL,"
        "  epoch INTEGER NOT NULL,"
        "  lease_generation INTEGER NOT NULL,"
        "  holder_id TEXT NOT NULL,"
        "  destination_runtime TEXT NOT NULL,"
        "  fencing_token TEXT NOT NULL,"
        "  issued_at REAL NOT NULL,"
        "  expires_at REAL NOT NULL"
        ");"
        "CREATE TABLE IF NOT EXISTS lease_history ("
        "  seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  agent_id TEXT NOT NULL,"
        "  lease_generation INTEGER NOT NULL,"
        "  holder_id TEXT NOT NULL,"
        "  action TEXT NOT NULL,"
        "  fencing_token TEXT,"
        "  timestamp REAL NOT NULL"
        ");";
    sqlite3_exec(db, schema, nullptr, nullptr, nullptr);
    sqlite3_close(db);
}

std::pair<std::optional<Lease>, std::optional<std::string>>
LeaseManager::acquire(const std::string& agent_id, const std::string& capsule_hash,
                      int epoch, const std::string& holder_id,
                      const std::string& destination_runtime) {
    sqlite3* db = nullptr;
    sqlite3_open(db_path_.c_str(), &db);
    sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr);

    // Check existing lease
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db, "SELECT * FROM leases WHERE agent_id = ?", -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);

    bool has_existing = false;
    std::string existing_holder;
    int existing_gen = 0;
    double existing_expires = 0;

    if (sqlite3_step(stmt) == SQLITE_ROW) {
        has_existing = true;
        existing_gen = sqlite3_column_int(stmt, 3);
        existing_holder = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
        existing_expires = sqlite3_column_double(stmt, 8);
    }
    sqlite3_finalize(stmt);

    // Check history for max generation
    int max_hist_gen = 0;
    sqlite3_prepare_v2(db, "SELECT MAX(lease_generation) as max_gen FROM lease_history WHERE agent_id = ?",
                       -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        auto val = sqlite3_column_int(stmt, 0);
        if (val > 0) max_hist_gen = val;
    }
    sqlite3_finalize(stmt);

    if (has_existing) {
        double now = epoch_seconds();
        if (now < existing_expires) {
            int remaining = static_cast<int>(existing_expires - now);
            sqlite3_exec(db, "ROLLBACK", nullptr, nullptr, nullptr);
            sqlite3_close(db);
            return {std::nullopt, "lease held by '" + existing_holder + "' gen=" +
                    std::to_string(existing_gen) + " for " + std::to_string(remaining) + "s"};
        }
    }

    int gen = std::max(has_existing ? existing_gen : 0, max_hist_gen) + 1;
    std::string fencing_token = generate_fencing_token();
    double now = epoch_seconds();
    double expires = now + ttl_;

    sqlite3_prepare_v2(db,
        "INSERT OR REPLACE INTO leases "
        "(agent_id, capsule_hash, epoch, lease_generation, holder_id, "
        "destination_runtime, fencing_token, issued_at, expires_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)", -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, capsule_hash.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 3, epoch);
    sqlite3_bind_int(stmt, 4, gen);
    sqlite3_bind_text(stmt, 5, holder_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 6, destination_runtime.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 7, fencing_token.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_double(stmt, 8, now);
    sqlite3_bind_double(stmt, 9, expires);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    // Insert history
    sqlite3_prepare_v2(db,
        "INSERT INTO lease_history "
        "(agent_id, lease_generation, holder_id, action, fencing_token, timestamp) "
        "VALUES (?,?,?,?,?,?)", -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gen);
    sqlite3_bind_text(stmt, 3, holder_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, "acquire", -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 5, fencing_token.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_double(stmt, 6, now);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);
    sqlite3_close(db);

    Lease lease;
    lease.agent_id = agent_id;
    lease.capsule_hash = capsule_hash;
    lease.epoch = epoch;
    lease.lease_generation = gen;
    lease.holder_id = holder_id;
    lease.destination_runtime = destination_runtime;
    lease.fencing_token = fencing_token;
    lease.issued_at = now;
    lease.expires_at = expires;

    return {lease, std::nullopt};
}

bool LeaseManager::release(const std::string& agent_id, const std::string& fencing_token) {
    sqlite3* db = nullptr;
    sqlite3_open(db_path_.c_str(), &db);
    sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr);

    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db, "SELECT * FROM leases WHERE agent_id = ?", -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);

    if (sqlite3_step(stmt) != SQLITE_ROW) {
        sqlite3_finalize(stmt);
        sqlite3_exec(db, "ROLLBACK", nullptr, nullptr, nullptr);
        sqlite3_close(db);
        return false;
    }

    std::string db_token = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
    int gen = sqlite3_column_int(stmt, 3);
    std::string holder = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
    sqlite3_finalize(stmt);

    if (db_token != fencing_token) {
        sqlite3_exec(db, "ROLLBACK", nullptr, nullptr, nullptr);
        sqlite3_close(db);
        return false;
    }

    sqlite3_prepare_v2(db, "DELETE FROM leases WHERE agent_id = ?", -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    sqlite3_prepare_v2(db,
        "INSERT INTO lease_history "
        "(agent_id, lease_generation, holder_id, action, fencing_token, timestamp) "
        "VALUES (?,?,?,?,?,?)", -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gen);
    sqlite3_bind_text(stmt, 3, holder.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, "release", -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 5, fencing_token.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_double(stmt, 6, epoch_seconds());
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);
    sqlite3_close(db);
    return true;
}

bool LeaseManager::validate_token(const std::string& agent_id,
                                   const std::string& fencing_token) const {
    sqlite3* db = nullptr;
    sqlite3_open(db_path_.c_str(), &db);

    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db, "SELECT fencing_token, expires_at FROM leases WHERE agent_id = ?",
                       -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);

    bool valid = false;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        std::string db_token = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
        double expires = sqlite3_column_double(stmt, 1);
        if (epoch_seconds() < expires && db_token == fencing_token)
            valid = true;
    }
    sqlite3_finalize(stmt);
    sqlite3_close(db);
    return valid;
}

std::optional<Lease> LeaseManager::get_current(const std::string& agent_id) const {
    sqlite3* db = nullptr;
    sqlite3_open(db_path_.c_str(), &db);

    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db, "SELECT * FROM leases WHERE agent_id = ?", -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, agent_id.c_str(), -1, SQLITE_TRANSIENT);

    std::optional<Lease> result;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        Lease l;
        l.agent_id = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
        l.capsule_hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        l.epoch = sqlite3_column_int(stmt, 2);
        l.lease_generation = sqlite3_column_int(stmt, 3);
        l.holder_id = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
        l.destination_runtime = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
        l.fencing_token = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        l.issued_at = sqlite3_column_double(stmt, 7);
        l.expires_at = sqlite3_column_double(stmt, 8);
        result = l;
    }
    sqlite3_finalize(stmt);
    sqlite3_close(db);
    return result;
}

bool LeaseManager::reject_stale(const std::string& agent_id,
                                 const std::string& stale_token) const {
    return !validate_token(agent_id, stale_token);
}

} // namespace hdar
