#include "hdar/store.hpp"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <algorithm>

namespace fs = std::filesystem;

namespace hdar {

// ── WorkspaceManifest ─────────────────────────────────────────

JsonValue WorkspaceManifest::to_json() const {
    JsonValue root = JsonValue::object();
    JsonValue files_arr = JsonValue::array();
    for (const auto& f : files) {
        JsonValue fo = JsonValue::object();
        fo["path"] = JsonValue::string(f.path);
        fo["hash"] = JsonValue::string(f.hash);
        fo["size"] = JsonValue::integer(static_cast<int64_t>(f.size));
        files_arr.push_back(std::move(fo));
    }
    root["files"] = std::move(files_arr);
    root["root_hash"] = JsonValue::string(root_hash);
    root["total_size"] = JsonValue::integer(static_cast<int64_t>(total_size));
    return root;
}

WorkspaceManifest WorkspaceManifest::from_json(const JsonValue& v) {
    WorkspaceManifest m;
    const auto& files_arr = v.get("files");
    if (files_arr.type == JsonValue::Type::Array) {
        for (const auto& f : files_arr.array_val) {
            FileEntry fe;
            fe.path = f.get("path").string_val;
            fe.hash = f.get("hash").string_val;
            fe.size = static_cast<size_t>(f.get("size").int_val);
            m.files.push_back(fe);
        }
    }
    m.root_hash = v.get("root_hash").string_val;
    m.total_size = static_cast<size_t>(v.get("total_size").int_val);
    return m;
}

// ── ContentStore ──────────────────────────────────────────────

ContentStore::ContentStore(const std::string& base_dir) : base_dir_(base_dir) {
    fs::create_directories(base_dir_);
    // Create subdirectory structure (sharded by first 2 hex chars)
    fs::create_directories(base_dir_ + "/blobs");
}

std::string ContentStore::blob_path(const std::string& hash) const {
    if (hash.size() < 2) return base_dir_ + "/blobs/" + hash;
    return base_dir_ + "/blobs/" + hash.substr(0, 2) + "/" + hash;
}

std::string ContentStore::ingest_file(const std::string& file_path) {
    auto bytes = read_file_to_bytes(file_path);
    return ingest_bytes(bytes);
}

std::string ContentStore::ingest_bytes(const std::vector<uint8_t>& data) {
    std::string hash = sha256_hex(data);
    std::string path = blob_path(hash);
    if (!fs::exists(path)) {
        fs::create_directories(fs::path(path).parent_path());
        write_bytes_to_file(path, data);
    }
    return hash;
}

std::vector<uint8_t> ContentStore::retrieve(const std::string& hash) const {
    std::string path = blob_path(hash);
    return read_file_to_bytes(path);
}

void ContentStore::scan_directory(const std::string& dir, const std::string& prefix,
                                   std::vector<FileEntry>& entries) const {
    for (const auto& entry : fs::directory_iterator(dir)) {
        std::string name = entry.path().filename().string();
        std::string rel = prefix.empty() ? name : prefix + "/" + name;

        if (entry.is_directory()) {
            scan_directory(entry.path().string(), rel, entries);
        } else if (entry.is_regular_file()) {
            auto bytes = read_file_to_bytes(entry.path().string());
            FileEntry fe;
            fe.path = rel;
            fe.hash = sha256_hex(bytes);
            fe.size = bytes.size();
            entries.push_back(std::move(fe));
        }
    }
}

WorkspaceManifest ContentStore::ingest_workspace(const std::string& dir_path) {
    WorkspaceManifest manifest;
    scan_directory(dir_path, "", manifest.files);

    // Sort by path for deterministic ordering
    std::sort(manifest.files.begin(), manifest.files.end(),
              [](const FileEntry& a, const FileEntry& b) { return a.path < b.path; });

    // Ingest all files and compute root hash
    JsonValue files_arr = JsonValue::array();
    size_t total = 0;
    for (const auto& f : manifest.files) {
        std::string full = dir_path + "/" + f.path;
        ingest_bytes(read_file_to_bytes(full));
        total += f.size;

        JsonValue fo = JsonValue::object();
        fo["path"] = JsonValue::string(f.path);
        fo["hash"] = JsonValue::string(f.hash);
        fo["size"] = JsonValue::integer(static_cast<int64_t>(f.size));
        files_arr.push_back(std::move(fo));
    }

    JsonValue root_obj = JsonValue::object();
    root_obj["files"] = std::move(files_arr);
    manifest.root_hash = sha256_json(root_obj);
    manifest.total_size = total;

    return manifest;
}

WorkspaceManifest ContentStore::hash_workspace(const std::string& dir_path) const {
    WorkspaceManifest manifest;
    scan_directory(dir_path, "", manifest.files);

    std::sort(manifest.files.begin(), manifest.files.end(),
              [](const FileEntry& a, const FileEntry& b) { return a.path < b.path; });

    JsonValue files_arr = JsonValue::array();
    size_t total = 0;
    for (const auto& f : manifest.files) {
        total += f.size;
        JsonValue fo = JsonValue::object();
        fo["path"] = JsonValue::string(f.path);
        fo["hash"] = JsonValue::string(f.hash);
        fo["size"] = JsonValue::integer(static_cast<int64_t>(f.size));
        files_arr.push_back(std::move(fo));
    }

    JsonValue root_obj = JsonValue::object();
    root_obj["files"] = std::move(files_arr);
    manifest.root_hash = sha256_json(root_obj);
    manifest.total_size = total;

    return manifest;
}

void ContentStore::restore_workspace(const WorkspaceManifest& manifest,
                                      const std::string& dest_dir) const {
    fs::create_directories(dest_dir);
    for (const auto& f : manifest.files) {
        std::string full = dest_dir + "/" + f.path;
        fs::create_directories(fs::path(full).parent_path());
        auto content = retrieve(f.hash);
        write_bytes_to_file(full, content);
    }
}

} // namespace hdar
