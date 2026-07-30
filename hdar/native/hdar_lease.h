// hdar_lease.h — SQLite-backed lease manager with fencing tokens.

#ifndef HDAR_LEASE_H
#define HDAR_LEASE_H

#include <string>
#include <cstdint>
#include <optional>
#include <mutex>

namespace hdar {

/// A fencing lease: exclusive ownership with a monotonically increasing token.
struct Lease {
    std::string agent_id;
    std::string capsule_hash;
    int64_t lease_generation;
    std::string fencing_token;  // UUID
    std::string holder_id;
    std::string runtime_id;
    double acquired_at;
    double expires_at;
    bool active;
};

/// SQLite-backed lease manager. Thread-safe.
class LeaseManager {
public:
    explicit LeaseManager(const std::string& db_path);
    ~LeaseManager();

    /// Acquire a lease for an agent. Returns lease or error string.
    std::pair<std::optional<Lease>, std::string> acquire(
        const std::string& agent_id,
        const std::string& capsule_hash,
        int64_t min_generation,
        const std::string& holder_id,
        const std::string& runtime_id,
        double ttl_seconds = 300.0
    );

    /// Release a lease. Must match fencing token.
    std::string release(const std::string& agent_id, const std::string& fencing_token);

    /// Force-release any active lease for an agent, regardless of token.
    /// Used by gateway before starting a new session.
    std::string force_release(const std::string& agent_id);

    /// Validate a fencing token. Returns true if valid and active.
    bool validate_token(const std::string& agent_id, const std::string& fencing_token);

    /// Invalidate (force-release) a lease. Used during destruction.
    std::string invalidate(const std::string& agent_id, const std::string& fencing_token);

    /// Get current lease for agent.
    std::optional<Lease> get_lease(const std::string& agent_id);

private:
    std::string db_path_;
    std::mutex mutex_;
    void* db_;  // sqlite3*

    void init_db();
    std::string generate_uuid();
};

/// A fencing invalidation receipt.
struct FencingInvalidation {
    std::string agent_id;
    int64_t lease_generation;
    std::string fencing_token;
    std::string holder_id;
    std::string runtime_id;
    double invalidated_at;
    std::string reason;

    std::string to_json() const;
    static FencingInvalidation from_json(const std::string& json);
};

} // namespace hdar

#endif // HDAR_LEASE_H
