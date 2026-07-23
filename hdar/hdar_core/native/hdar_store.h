// hdar_store.h — Content-addressed capsule store (native C++).

#ifndef HDAR_STORE_H
#define HDAR_STORE_H

#include <string>
#include <vector>
#include <cstdint>
#include <memory>
#include "hdar_crypto.h"

namespace hdar {

/// A workspace manifest entry: filename + content hash.
struct WorkspaceEntry {
    std::string relative_path;
    std::string content_hash;  // SHA-256 hex
    size_t size;
};

/// A workspace manifest: list of entries + directory hash.
struct WorkspaceManifest {
    std::vector<WorkspaceEntry> entries;
    std::string manifest_hash;  // SHA-256 of all entry hashes

    std::string to_json() const;
    static WorkspaceManifest from_json(const std::string& json);
};

/// Content-addressed store. Blocks stored by SHA-256 hash.
class ContentStore {
public:
    explicit ContentStore(const std::string& root_dir);

    /// Store a block of data. Returns its SHA-256 hash.
    std::string store_block(const uint8_t* data, size_t len);
    std::string store_block(const std::string& data);

    /// Retrieve a block by hash. Returns empty vector if not found.
    std::vector<uint8_t> get_block(const std::string& hash) const;

    /// Check if a block exists.
    bool has_block(const std::string& hash) const;

    /// Store a workspace directory. Returns manifest.
    WorkspaceManifest store_workspace(const std::string& dir_path);

    /// Restore a workspace to a directory.
    bool restore_workspace(const WorkspaceManifest& manifest, const std::string& dest_path) const;

    /// Get store root.
    const std::string& root() const { return root_dir_; }

private:
    std::string root_dir_;
    std::string block_path(const std::string& hash) const;
};

/// A continuity capsule: signed state snapshot.
struct Capsule {
    // Lineage
    int epoch;
    std::string agent_id;
    std::string agent_name;
    std::string parent_hash;  // empty for genesis

    // State
    std::string objective;
    std::string continuation_point;
    WorkspaceManifest workspace;

    // Capabilities (JSON array)
    std::string capabilities_json;

    // Cryptographic proof
    std::string manifest_hash;      // SHA-256 of canonical form
    std::string owner_signature;    // Ed25519 signature hex
    std::string owner_public_key;   // Owner's public key hex

    // Receipts
    std::vector<std::string> receipt_chain;  // JSON receipts

    /// Canonical form for signing (deterministic JSON).
    std::string canonical_form() const;

    /// Serialize to JSON.
    std::string to_json() const;
    static Capsule from_json(const std::string& json);

    /// Compute and set manifest hash.
    void compute_hash();
};

} // namespace hdar

#endif // HDAR_STORE_H
