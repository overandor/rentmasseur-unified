// hdar_store.cpp — Content-addressed capsule store (pure C++).

#include "hdar_store.h"
#include <fstream>
#include <sstream>
#include <sys/stat.h>
#include <dirent.h>

namespace hdar {

// ─── WorkspaceManifest ─────────────────────────────────────────────────

std::string WorkspaceManifest::to_json() const {
    std::ostringstream ss;
    ss << "{\"entries\":[";
    for (size_t i = 0; i < entries.size(); i++) {
        if (i > 0) ss << ",";
        ss << "{\"path\":\"" << entries[i].relative_path
           << "\",\"hash\":\"" << entries[i].content_hash
           << "\",\"size\":" << entries[i].size << "}";
    }
    ss << "],\"manifest_hash\":\"" << manifest_hash << "\"}";
    return ss.str();
}

WorkspaceManifest WorkspaceManifest::from_json(const std::string& json) {
    WorkspaceManifest m;
    // Simple JSON parsing for our flat structure
    size_t pos = json.find("\"manifest_hash\"");
    if (pos != std::string::npos) {
        size_t s = json.find("\"", pos + 15) + 1;
        size_t e = json.find("\"", s);
        m.manifest_hash = json.substr(s, e - s);
    }
    // Parse entries
    size_t epos = json.find("\"entries\"");
    if (epos != std::string::npos) {
        size_t arr_start = json.find("[", epos);
        size_t arr_end = json.find("]", arr_start);
        std::string arr = json.substr(arr_start + 1, arr_end - arr_start - 1);

        size_t pos2 = 0;
        while ((pos2 = arr.find("\"path\"", pos2)) != std::string::npos) {
            WorkspaceEntry we;
            size_t s = arr.find("\"", pos2 + 6) + 1;
            size_t e = arr.find("\"", s);
            we.relative_path = arr.substr(s, e - s);

            size_t hpos = arr.find("\"hash\"", e);
            s = arr.find("\"", hpos + 6) + 1;
            e = arr.find("\"", s);
            we.content_hash = arr.substr(s, e - s);

            size_t szpos = arr.find("\"size\"", e);
            s = arr.find(":", szpos + 6) + 1;
            e = arr.find_first_of(",}", s);
            we.size = std::stoul(arr.substr(s, e - s));

            m.entries.push_back(we);
            pos2 = e;
        }
    }
    return m;
}

// ─── ContentStore ──────────────────────────────────────────────────────

ContentStore::ContentStore(const std::string& root_dir) : root_dir_(root_dir) {
    mkdir(root_dir_.c_str(), 0755);
    mkdir((root_dir_ + "/blocks").c_str(), 0755);
}

std::string ContentStore::block_path(const std::string& hash) const {
    if (hash.size() < 2) return root_dir_ + "/blocks/" + hash;
    return root_dir_ + "/blocks/" + hash.substr(0, 2) + "/" + hash;
}

std::string ContentStore::store_block(const uint8_t* data, size_t len) {
    std::string hash = sha256_hex(data, len);
    std::string path = block_path(hash);

    if (hash.size() >= 2) {
        mkdir((root_dir_ + "/blocks/" + hash.substr(0, 2)).c_str(), 0755);
    }

    struct stat st;
    if (stat(path.c_str(), &st) == 0) return hash;

    std::ofstream f(path, std::ios::binary);
    f.write((const char*)data, len);
    return hash;
}

std::string ContentStore::store_block(const std::string& data) {
    return store_block((const uint8_t*)data.data(), data.size());
}

std::vector<uint8_t> ContentStore::get_block(const std::string& hash) const {
    std::string path = block_path(hash);
    std::ifstream f(path, std::ios::binary);
    if (!f) return {};
    return std::vector<uint8_t>((std::istreambuf_iterator<char>(f)),
                                 std::istreambuf_iterator<char>());
}

bool ContentStore::has_block(const std::string& hash) const {
    struct stat st;
    return stat(block_path(hash).c_str(), &st) == 0;
}

// Recursive directory walk
static void walk_dir(const std::string& base, const std::string& rel,
                      ContentStore& store, WorkspaceManifest& manifest,
                      std::string& combined) {
    std::string full = base + "/" + rel;
    DIR* dir = opendir(full.c_str());
    if (!dir) return;

    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        std::string name = entry->d_name;
        if (name == "." || name == "..") continue;

        std::string child_rel = rel.empty() ? name : rel + "/" + name;
        std::string child_full = base + "/" + child_rel;

        struct stat st;
        if (stat(child_full.c_str(), &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            walk_dir(base, child_rel, store, manifest, combined);
        } else {
            std::ifstream f(child_full, std::ios::binary);
            if (!f) continue;
            std::vector<uint8_t> data((std::istreambuf_iterator<char>(f)),
                                       std::istreambuf_iterator<char>());

            std::string hash = sha256_hex(data.data(), data.size());
            store.store_block(data.data(), data.size());

            WorkspaceEntry we;
            we.relative_path = child_rel;
            we.content_hash = hash;
            we.size = data.size();
            manifest.entries.push_back(we);
            combined += hash;
        }
    }
    closedir(dir);
}

WorkspaceManifest ContentStore::store_workspace(const std::string& dir_path) {
    WorkspaceManifest manifest;
    std::string combined;
    walk_dir(dir_path, "", *this, manifest, combined);
    manifest.manifest_hash = sha256_hex(combined);
    return manifest;
}

bool ContentStore::restore_workspace(const WorkspaceManifest& manifest, const std::string& dest_path) const {
    mkdir(dest_path.c_str(), 0755);

    for (const auto& entry : manifest.entries) {
        std::string full_path = dest_path + "/" + entry.relative_path;

        size_t pos = 0;
        while ((pos = full_path.find('/', pos + 1)) != std::string::npos) {
            mkdir(full_path.substr(0, pos).c_str(), 0755);
        }

        auto data = get_block(entry.content_hash);
        if (data.empty()) return false;

        std::ofstream f(full_path, std::ios::binary);
        f.write((const char*)data.data(), data.size());
    }
    return true;
}

// ─── Capsule ───────────────────────────────────────────────────────────

std::string Capsule::canonical_form() const {
    // Fields in alphabetical key order to match Python's json.dumps(sort_keys=True)
    std::ostringstream ss;
    ss << "{"
       << "\"agent_id\":\"" << agent_id << "\""
       << ",\"agent_name\":\"" << agent_name << "\""
       << ",\"capabilities\":" << capabilities_json
       << ",\"continuation_point\":\"" << continuation_point << "\""
       << ",\"epoch\":" << epoch
       << ",\"objective\":\"" << objective << "\""
       << ",\"parent_hash\":\"" << parent_hash << "\""
       << ",\"workspace_manifest_hash\":\"" << workspace.manifest_hash << "\""
       << "}";
    return ss.str();
}

void Capsule::compute_hash() {
    manifest_hash = sha256_hex(canonical_form());
}

std::string Capsule::to_json() const {
    std::ostringstream ss;
    ss << "{"
       << "\"epoch\":" << epoch
       << ",\"agent_id\":\"" << agent_id << "\""
       << ",\"agent_name\":\"" << agent_name << "\""
       << ",\"parent_hash\":\"" << parent_hash << "\""
       << ",\"objective\":\"" << objective << "\""
       << ",\"continuation_point\":\"" << continuation_point << "\""
       << ",\"workspace\":" << workspace.to_json()
       << ",\"capabilities\":" << capabilities_json
       << ",\"manifest_hash\":\"" << manifest_hash << "\""
       << ",\"owner_signature\":\"" << owner_signature << "\""
       << ",\"owner_public_key\":\"" << owner_public_key << "\""
       << ",\"receipt_chain\":[";
    for (size_t i = 0; i < receipt_chain.size(); i++) {
        if (i > 0) ss << ",";
        // Escape embedded quotes and backslashes in receipt JSON
        std::string escaped;
        for (char c : receipt_chain[i]) {
            if (c == '"') escaped += "\\\"";
            else if (c == '\\') escaped += "\\\\";
            else escaped += c;
        }
        ss << "\"" << escaped << "\"";
    }
    ss << "]}";
    return ss.str();
}

Capsule Capsule::from_json(const std::string& json) {
    Capsule c;

    // Helper: find string value for a top-level key (value is in quotes)
    auto find_str = [&](const std::string& key) -> std::string {
        size_t pos = json.find("\"" + key + "\"");
        if (pos == std::string::npos) return "";
        size_t s = json.find("\"", pos + key.size() + 2) + 1;
        size_t e = json.find("\"", s);
        return json.substr(s, e - s);
    };
    // Helper: find int value for a key
    auto find_int = [&](const std::string& key) -> int {
        size_t pos = json.find("\"" + key + "\"");
        if (pos == std::string::npos) return 0;
        size_t s = json.find(":", pos + key.size() + 2) + 1;
        size_t e = json.find_first_of(",}", s);
        return std::stoi(json.substr(s, e - s));
    };
    // Helper: find a JSON value (string, array, or object) for a key
    auto find_json_value = [&](const std::string& key) -> std::string {
        size_t pos = json.find("\"" + key + "\"");
        if (pos == std::string::npos) return "";
        size_t s = json.find(":", pos + key.size() + 2) + 1;
        // Skip whitespace
        while (s < json.size() && (json[s] == ' ' || json[s] == '\n' || json[s] == '\t')) s++;
        if (s >= json.size()) return "";
        char open = json[s];
        if (open == '[') {
            // Find matching ]
            int depth = 0;
            size_t e = s;
            for (; e < json.size(); e++) {
                if (json[e] == '[') depth++;
                else if (json[e] == ']') { depth--; if (depth == 0) { e++; break; } }
            }
            return json.substr(s, e - s);
        } else if (open == '{') {
            int depth = 0;
            size_t e = s;
            for (; e < json.size(); e++) {
                if (json[e] == '{') depth++;
                else if (json[e] == '}') { depth--; if (depth == 0) { e++; break; } }
            }
            return json.substr(s, e - s);
        } else if (open == '"') {
            size_t e = json.find("\"", s + 1);
            return json.substr(s, e - s + 1);
        } else {
            size_t e = json.find_first_of(",}", s);
            return json.substr(s, e - s);
        }
    };

    c.epoch = find_int("epoch");
    c.agent_id = find_str("agent_id");
    c.agent_name = find_str("agent_name");
    c.parent_hash = find_str("parent_hash");
    c.objective = find_str("objective");
    c.continuation_point = find_str("continuation_point");
    c.owner_signature = find_str("owner_signature");
    c.owner_public_key = find_str("owner_public_key");
    c.capabilities_json = find_json_value("capabilities");

    // Parse workspace manifest hash from nested workspace object
    size_t ws_pos = json.find("\"workspace\"");
    if (ws_pos != std::string::npos) {
        size_t mh_pos = json.find("\"manifest_hash\"", ws_pos);
        if (mh_pos != std::string::npos) {
            size_t s = json.find("\"", mh_pos + 15) + 1;
            size_t e = json.find("\"", s);
            c.workspace.manifest_hash = json.substr(s, e - s);
        }
    }

    // Parse capsule's own manifest_hash — last occurrence
    size_t last_mh = json.rfind("\"manifest_hash\"");
    if (last_mh != std::string::npos) {
        // Make sure this isn't the workspace one
        if (ws_pos == std::string::npos || last_mh > ws_pos + 100) {
            size_t s = json.find("\"", last_mh + 15) + 1;
            size_t e = json.find("\"", s);
            c.manifest_hash = json.substr(s, e - s);
        }
    }

    return c;
}

} // namespace hdar
