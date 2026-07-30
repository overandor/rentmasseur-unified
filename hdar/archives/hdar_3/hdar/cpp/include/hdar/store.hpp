#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <vector>
#include <map>

namespace hdar {

// ── Content-addressed store ───────────────────────────────────

struct FileEntry {
    std::string path;       // relative path within workspace
    std::string hash;       // SHA-256 hex of content
    size_t size = 0;
};

struct WorkspaceManifest {
    std::vector<FileEntry> files;
    std::string root_hash;  // SHA-256 over canonical JSON of file list
    size_t total_size = 0;

    JsonValue to_json() const;
    static WorkspaceManifest from_json(const JsonValue& v);
};

class ContentStore {
public:
    explicit ContentStore(const std::string& base_dir);

    // Ingest a single file, return its content hash
    std::string ingest_file(const std::string& file_path);

    // Ingest raw bytes, return content hash
    std::string ingest_bytes(const std::vector<uint8_t>& data);

    // Retrieve content by hash
    std::vector<uint8_t> retrieve(const std::string& hash) const;

    // Ingest an entire workspace directory
    WorkspaceManifest ingest_workspace(const std::string& dir_path);

    // Hash a workspace directory without ingesting
    WorkspaceManifest hash_workspace(const std::string& dir_path) const;

    // Restore a workspace from a manifest
    void restore_workspace(const WorkspaceManifest& manifest, const std::string& dest_dir) const;

    const std::string& base_directory() const { return base_dir_; }

private:
    std::string base_dir_;

    std::string blob_path(const std::string& hash) const;
    void scan_directory(const std::string& dir, const std::string& prefix,
                        std::vector<FileEntry>& entries) const;
};

} // namespace hdar
