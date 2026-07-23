#pragma once

#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>
#include <array>
#include <map>
#include <stdexcept>
#include <sstream>
#include <iomanip>
#include <fstream>

namespace hdar {

// ── Forward declarations ──────────────────────────────────────

class OwnerKeyPair;
class PublicKey;
class HostKeyPair;

// ── Hex utilities ─────────────────────────────────────────────

std::string to_hex(const uint8_t* data, size_t len);
std::string to_hex(const std::vector<uint8_t>& data);
std::vector<uint8_t> from_hex(const std::string& hex);

// ── SHA-256 ───────────────────────────────────────────────────

std::string sha256_hex(const uint8_t* data, size_t len);
std::string sha256_hex(const std::string& data);
std::string sha256_hex(const std::vector<uint8_t>& data);

// ── Canonical JSON ────────────────────────────────────────────
// Stable serialization: sorted keys, no whitespace, ASCII-only.
// Uses nlohmann/json internally but we implement a minimal canonical
// serializer to avoid the dependency.

struct JsonValue {
    enum class Type { Null, Bool, Int, Double, String, Array, Object };
    Type type = Type::Null;
    bool bool_val = false;
    int64_t int_val = 0;
    double double_val = 0.0;
    std::string string_val;
    std::vector<JsonValue> array_val;
    std::map<std::string, JsonValue> object_val;

    static JsonValue null() { return {}; }
    static JsonValue boolean(bool b) { JsonValue v; v.type = Type::Bool; v.bool_val = b; return v; }
    static JsonValue integer(int64_t i) { JsonValue v; v.type = Type::Int; v.int_val = i; return v; }
    static JsonValue number(double d) { JsonValue v; v.type = Type::Double; v.double_val = d; return v; }
    static JsonValue string(const std::string& s) { JsonValue v; v.type = Type::String; v.string_val = s; return v; }
    static JsonValue array() { JsonValue v; v.type = Type::Array; return v; }
    static JsonValue object() { JsonValue v; v.type = Type::Object; return v; }

    JsonValue& operator[](const std::string& key) {
        type = Type::Object;
        return object_val[key];
    }
    JsonValue& operator[](size_t i) {
        type = Type::Array;
        if (i >= array_val.size()) array_val.resize(i + 1);
        return array_val[i];
    }
    void push_back(JsonValue v) {
        type = Type::Array;
        array_val.push_back(std::move(v));
    }
    bool has(const std::string& key) const {
        return type == Type::Object && object_val.count(key) > 0;
    }
    const JsonValue& get(const std::string& key) const {
        static JsonValue null_val;
        auto it = object_val.find(key);
        if (it == object_val.end()) return null_val;
        return it->second;
    }
};

// Canonical JSON serialization (sorted keys, compact, ASCII-escaped)
std::string canonical_json(const JsonValue& v);
std::vector<uint8_t> canonical_json_bytes(const JsonValue& v);

// JSON parser
JsonValue parse_json(const std::string& text);
JsonValue parse_json(const std::vector<uint8_t>& bytes);

// SHA-256 over canonical JSON
std::string sha256_json(const JsonValue& v);

// ── Ed25519 keys ──────────────────────────────────────────────

class PublicKey {
public:
    static constexpr size_t KEY_SIZE = 32;
    std::array<uint8_t, KEY_SIZE> raw{};

    PublicKey() = default;
    explicit PublicKey(const std::array<uint8_t, KEY_SIZE>& k) : raw(k) {}

    std::string hex() const;
    std::string fingerprint() const; // first 16 hex chars of SHA-256(raw)

    bool verify(const uint8_t* data, size_t len, const uint8_t* sig) const;
    bool verify(const std::vector<uint8_t>& data, const std::vector<uint8_t>& sig) const;
    bool verify_hex(const std::vector<uint8_t>& data, const std::string& sig_hex) const;
    bool verify_json(const JsonValue& obj, const std::string& sig_hex) const;

    static PublicKey from_hex(const std::string& hex);
};

class PrivateKey {
public:
    static constexpr size_t KEY_SIZE = 64;
    std::array<uint8_t, KEY_SIZE> raw{};

    PrivateKey() = default;
    explicit PrivateKey(const std::array<uint8_t, KEY_SIZE>& k) : raw(k) {}

    std::string hex() const;
    PublicKey public_key() const;

    std::vector<uint8_t> sign(const uint8_t* data, size_t len) const;
    std::vector<uint8_t> sign(const std::vector<uint8_t>& data) const;
    std::string sign_hex(const std::vector<uint8_t>& data) const;
    std::string sign_json(const JsonValue& obj) const;

    static PrivateKey from_hex(const std::string& hex);
    static PrivateKey generate();
};

class OwnerKeyPair {
public:
    PrivateKey private_key;
    PublicKey public_key;

    OwnerKeyPair() = default;
    explicit OwnerKeyPair(const PrivateKey& sk);

    static OwnerKeyPair generate();
    static OwnerKeyPair from_private_hex(const std::string& hex);

    std::string fingerprint() const { return public_key.fingerprint(); }
    std::string public_key_hex() const { return public_key.hex(); }
    std::string private_key_hex() const { return private_key.hex(); }

    std::string sign_json(const JsonValue& obj) const;
    std::string sign_bytes(const std::vector<uint8_t>& data) const;

    PublicKey to_public() const { return public_key; }

    void save(const std::string& path) const;
    static OwnerKeyPair load(const std::string& path);
};

class HostKeyPair {
public:
    PrivateKey private_key;
    PublicKey public_key;
    std::string host_id;

    HostKeyPair() = default;

    static HostKeyPair generate(const std::string& host_id = "");

    std::string fingerprint() const { return public_key.fingerprint(); }
    std::string public_key_hex() const { return public_key.hex(); }

    std::string sign_json(const JsonValue& obj) const;
    std::string sign_bytes(const std::vector<uint8_t>& data) const;

    PublicKey to_public() const { return public_key; }
};

// ── UUID generation ───────────────────────────────────────────

std::string generate_uuid_hex();
std::string generate_agent_id();
std::string generate_fencing_token();

// ── File I/O helpers ──────────────────────────────────────────

std::string read_file_to_string(const std::string& path);
std::vector<uint8_t> read_file_to_bytes(const std::string& path);
void write_string_to_file(const std::string& path, const std::string& content);
void write_bytes_to_file(const std::string& path, const std::vector<uint8_t>& data);

// ── Time ──────────────────────────────────────────────────────

double epoch_seconds();

} // namespace hdar
