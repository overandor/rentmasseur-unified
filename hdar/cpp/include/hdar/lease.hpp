#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <optional>

namespace hdar {

static constexpr int DEFAULT_LEASE_TTL = 900; // 15 minutes

struct Lease {
    std::string agent_id;
    std::string capsule_hash;
    int epoch = 0;
    int lease_generation = 0;
    std::string holder_id;
    std::string destination_runtime;
    std::string fencing_token;
    double issued_at = 0.0;
    double expires_at = 0.0;

    bool is_expired() const;
    JsonValue to_json() const;
};

class LeaseManager {
public:
    LeaseManager(const std::string& db_path, int ttl = DEFAULT_LEASE_TTL);

    std::pair<std::optional<Lease>, std::optional<std::string>>
    acquire(const std::string& agent_id, const std::string& capsule_hash,
            int epoch, const std::string& holder_id,
            const std::string& destination_runtime);

    bool release(const std::string& agent_id, const std::string& fencing_token);
    bool validate_token(const std::string& agent_id, const std::string& fencing_token) const;
    std::optional<Lease> get_current(const std::string& agent_id) const;
    bool reject_stale(const std::string& agent_id, const std::string& stale_token) const;

private:
    std::string db_path_;
    int ttl_;
    void init_schema();
};

} // namespace hdar
