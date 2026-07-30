#pragma once

#include "hdar/crypto.hpp"
#include "hdar/store.hpp"
#include "hdar/seal.hpp"
#include <string>

namespace hdar {

class CapsuleRestorer {
public:
    explicit CapsuleRestorer(ContentStore& store);

    // Load capsule from JSON file
    CapsuleManifest load_capsule(const std::string& capsule_path) const;

    // Verify manifest Ed25519 signature and hash
    bool verify_manifest(const CapsuleManifest& manifest, const PublicKey& owner_pk) const;

    // Verify embedded receipt chain
    bool verify_receipts(const CapsuleManifest& manifest, const PublicKey& owner_pk) const;

    // Restore workspace from capsule
    std::pair<WorkspaceManifest, bool> restore_workspace(
        const CapsuleManifest& manifest, const std::string& dest_dir) const;

    // Full restoration
    JsonValue restore(const std::string& capsule_path,
                      const std::string& dest_dir,
                      const PublicKey* owner_public_key = nullptr) const;

private:
    ContentStore& store_;
};

} // namespace hdar
