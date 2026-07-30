#include "hdar/crypto.hpp"

#include <sodium.h>
#include <random>
#include <chrono>
#include <algorithm>
#include <cstring>
#include <sys/stat.h>

namespace hdar {

// ── Hex utilities ─────────────────────────────────────────────

std::string to_hex(const uint8_t* data, size_t len) {
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (size_t i = 0; i < len; ++i)
        oss << std::setw(2) << static_cast<int>(data[i]);
    return oss.str();
}

std::string to_hex(const std::vector<uint8_t>& data) {
    return to_hex(data.data(), data.size());
}

std::vector<uint8_t> from_hex(const std::string& hex) {
    std::vector<uint8_t> out;
    out.reserve(hex.size() / 2);
    for (size_t i = 0; i + 1 < hex.size(); i += 2) {
        auto nibble = [](char c) -> int {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            if (c >= 'A' && c <= 'F') return c - 'A' + 10;
            throw std::runtime_error("invalid hex character");
        };
        out.push_back(static_cast<uint8_t>((nibble(hex[i]) << 4) | nibble(hex[i + 1])));
    }
    return out;
}

// ── SHA-256 ───────────────────────────────────────────────────

std::string sha256_hex(const uint8_t* data, size_t len) {
    uint8_t hash[crypto_hash_sha256_BYTES];
    crypto_hash_sha256(hash, data, len);
    return to_hex(hash, crypto_hash_sha256_BYTES);
}

std::string sha256_hex(const std::string& data) {
    return sha256_hex(reinterpret_cast<const uint8_t*>(data.data()), data.size());
}

std::string sha256_hex(const std::vector<uint8_t>& data) {
    return sha256_hex(data.data(), data.size());
}

// ── Canonical JSON ────────────────────────────────────────────

static void escape_json_string(std::ostringstream& oss, const std::string& s) {
    oss << '"';
    for (unsigned char c : s) {
        switch (c) {
            case '"':  oss << "\\\""; break;
            case '\\': oss << "\\\\"; break;
            case '\b': oss << "\\b"; break;
            case '\f': oss << "\\f"; break;
            case '\n': oss << "\\n"; break;
            case '\r': oss << "\\r"; break;
            case '\t': oss << "\\t"; break;
            default:
                if (c < 0x20) {
                    oss << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                        << static_cast<int>(c) << std::dec;
                } else {
                    oss << static_cast<char>(c);
                }
        }
    }
    oss << '"';
}

static void canonical_json_impl(std::ostringstream& oss, const JsonValue& v) {
    switch (v.type) {
        case JsonValue::Type::Null:
            oss << "null";
            break;
        case JsonValue::Type::Bool:
            oss << (v.bool_val ? "true" : "false");
            break;
        case JsonValue::Type::Int:
            oss << v.int_val;
            break;
        case JsonValue::Type::Double: {
            // Match Python's json.dumps default float formatting
            oss << std::setprecision(17) << v.double_val;
            break;
        }
        case JsonValue::Type::String:
            escape_json_string(oss, v.string_val);
            break;
        case JsonValue::Type::Array:
            oss << '[';
            for (size_t i = 0; i < v.array_val.size(); ++i) {
                if (i > 0) oss << ',';
                canonical_json_impl(oss, v.array_val[i]);
            }
            oss << ']';
            break;
        case JsonValue::Type::Object:
            oss << '{';
            bool first = true;
            // std::map keeps keys sorted
            for (const auto& [key, val] : v.object_val) {
                if (!first) oss << ',';
                first = false;
                escape_json_string(oss, key);
                oss << ':';
                canonical_json_impl(oss, val);
            }
            oss << '}';
            break;
    }
}

std::string canonical_json(const JsonValue& v) {
    std::ostringstream oss;
    canonical_json_impl(oss, v);
    return oss.str();
}

std::vector<uint8_t> canonical_json_bytes(const JsonValue& v) {
    std::string s = canonical_json(v);
    return std::vector<uint8_t>(s.begin(), s.end());
}

std::string sha256_json(const JsonValue& v) {
    std::string s = canonical_json(v);
    return sha256_hex(reinterpret_cast<const uint8_t*>(s.data()), s.size());
}

// ── JSON Parser ───────────────────────────────────────────────

namespace {

class JsonParser {
public:
    JsonParser(const std::string& s) : input_(s), pos_(0) {}

    JsonValue parse() {
        skip_ws();
        JsonValue v = parse_value();
        skip_ws();
        return v;
    }

private:
    const std::string& input_;
    size_t pos_;

    void skip_ws() {
        while (pos_ < input_.size() &&
               (input_[pos_] == ' ' || input_[pos_] == '\t' ||
                input_[pos_] == '\n' || input_[pos_] == '\r'))
            ++pos_;
    }

    char peek() {
        if (pos_ >= input_.size()) throw std::runtime_error("unexpected end of JSON");
        return input_[pos_];
    }

    char next() {
        if (pos_ >= input_.size()) throw std::runtime_error("unexpected end of JSON");
        return input_[pos_++];
    }

    void expect(char c) {
        skip_ws();
        if (peek() != c) throw std::runtime_error(std::string("expected '") + c + "'");
        ++pos_;
    }

    JsonValue parse_value() {
        skip_ws();
        char c = peek();
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == '"') return parse_string();
        if (c == 't' || c == 'f') return parse_bool();
        if (c == 'n') return parse_null();
        return parse_number();
    }

    JsonValue parse_object() {
        JsonValue obj = JsonValue::object();
        expect('{');
        skip_ws();
        if (peek() == '}') { ++pos_; return obj; }
        while (true) {
            skip_ws();
            std::string key = parse_string_raw();
            expect(':');
            JsonValue val = parse_value();
            obj.object_val[key] = std::move(val);
            skip_ws();
            char c = next();
            if (c == '}') break;
            if (c != ',') throw std::runtime_error("expected ',' or '}' in object");
        }
        return obj;
    }

    JsonValue parse_array() {
        JsonValue arr = JsonValue::array();
        expect('[');
        skip_ws();
        if (peek() == ']') { ++pos_; return arr; }
        while (true) {
            JsonValue val = parse_value();
            arr.array_val.push_back(std::move(val));
            skip_ws();
            char c = next();
            if (c == ']') break;
            if (c != ',') throw std::runtime_error("expected ',' or ']' in array");
        }
        return arr;
    }

    JsonValue parse_string() {
        return JsonValue::string(parse_string_raw());
    }

    std::string parse_string_raw() {
        skip_ws();
        if (peek() != '"') throw std::runtime_error("expected string");
        ++pos_;
        std::string result;
        while (pos_ < input_.size()) {
            char c = input_[pos_++];
            if (c == '"') return result;
            if (c == '\\') {
                if (pos_ >= input_.size()) throw std::runtime_error("unterminated escape");
                char esc = input_[pos_++];
                switch (esc) {
                    case '"': result += '"'; break;
                    case '\\': result += '\\'; break;
                    case '/': result += '/'; break;
                    case 'n': result += '\n'; break;
                    case 't': result += '\t'; break;
                    case 'r': result += '\r'; break;
                    case 'b': result += '\b'; break;
                    case 'f': result += '\f'; break;
                    case 'u': {
                        if (pos_ + 4 > input_.size()) throw std::runtime_error("bad unicode escape");
                        std::string hex = input_.substr(pos_, 4);
                        pos_ += 4;
                        unsigned int cp = std::stoul(hex, nullptr, 16);
                        if (cp < 0x80) result += static_cast<char>(cp);
                        else if (cp < 0x800) {
                            result += static_cast<char>(0xC0 | (cp >> 6));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        } else {
                            result += static_cast<char>(0xE0 | (cp >> 12));
                            result += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        }
                        break;
                    }
                    default: result += esc; break;
                }
            } else {
                result += c;
            }
        }
        throw std::runtime_error("unterminated string");
    }

    JsonValue parse_bool() {
        if (input_.substr(pos_, 4) == "true") { pos_ += 4; return JsonValue::boolean(true); }
        if (input_.substr(pos_, 5) == "false") { pos_ += 5; return JsonValue::boolean(false); }
        throw std::runtime_error("invalid boolean");
    }

    JsonValue parse_null() {
        if (input_.substr(pos_, 4) == "null") { pos_ += 4; return JsonValue::null(); }
        throw std::runtime_error("invalid null");
    }

    JsonValue parse_number() {
        size_t start = pos_;
        if (peek() == '-') ++pos_;
        while (pos_ < input_.size() &&
               (std::isdigit(static_cast<unsigned char>(input_[pos_])) ||
                input_[pos_] == '.' || input_[pos_] == 'e' || input_[pos_] == 'E' ||
                input_[pos_] == '+' || input_[pos_] == '-'))
            ++pos_;
        std::string num_str = input_.substr(start, pos_ - start);
        if (num_str.find('.') != std::string::npos ||
            num_str.find('e') != std::string::npos ||
            num_str.find('E') != std::string::npos) {
            return JsonValue::number(std::stod(num_str));
        }
        return JsonValue::integer(std::stoll(num_str));
    }
};

} // anonymous namespace

JsonValue parse_json(const std::string& text) {
    JsonParser parser(text);
    return parser.parse();
}

JsonValue parse_json(const std::vector<uint8_t>& bytes) {
    return parse_json(std::string(bytes.begin(), bytes.end()));
}

// ── Ed25519 PublicKey ─────────────────────────────────────────

std::string PublicKey::hex() const {
    return to_hex(raw.data(), raw.size());
}

std::string PublicKey::fingerprint() const {
    std::string h = sha256_hex(raw.data(), raw.size());
    return h.substr(0, 16);
}

bool PublicKey::verify(const uint8_t* data, size_t len, const uint8_t* sig) const {
    return crypto_sign_verify_detached(sig, data, len, raw.data()) == 0;
}

bool PublicKey::verify(const std::vector<uint8_t>& data, const std::vector<uint8_t>& sig) const {
    if (sig.size() != crypto_sign_BYTES) return false;
    return verify(data.data(), data.size(), sig.data());
}
// Note: sig is already std::vector<uint8_t>, this is fine

bool PublicKey::verify_hex(const std::vector<uint8_t>& data, const std::string& sig_hex) const {
    auto sig = ::hdar::from_hex(sig_hex);
    if (sig.size() != crypto_sign_BYTES) return false;
    return verify(data.data(), data.size(), sig.data());
}

bool PublicKey::verify_json(const JsonValue& obj, const std::string& sig_hex) const {
    auto bytes = canonical_json_bytes(obj);
    return verify_hex(bytes, sig_hex);
}

PublicKey PublicKey::from_hex(const std::string& hex_str) {
    auto bytes = ::hdar::from_hex(hex_str);
    if (bytes.size() != KEY_SIZE)
        throw std::runtime_error("invalid public key length");
    PublicKey pk;
    std::memcpy(pk.raw.data(), bytes.data(), KEY_SIZE);
    return pk;
}

// ── Ed25519 PrivateKey ────────────────────────────────────────

std::string PrivateKey::hex() const {
    return to_hex(raw.data(), raw.size());
}

PublicKey PrivateKey::public_key() const {
    PublicKey pk;
    crypto_sign_ed25519_sk_to_pk(pk.raw.data(), raw.data());
    return pk;
}

std::vector<uint8_t> PrivateKey::sign(const uint8_t* data, size_t len) const {
    uint8_t sig[crypto_sign_BYTES];
    crypto_sign_detached(sig, nullptr, data, len, raw.data());
    return std::vector<uint8_t>(sig, sig + crypto_sign_BYTES);
}

std::vector<uint8_t> PrivateKey::sign(const std::vector<uint8_t>& data) const {
    return sign(data.data(), data.size());
}

std::string PrivateKey::sign_hex(const std::vector<uint8_t>& data) const {
    auto sig = sign(data);
    return to_hex(sig);
}

std::string PrivateKey::sign_json(const JsonValue& obj) const {
    auto bytes = canonical_json_bytes(obj);
    return sign_hex(bytes);
}

PrivateKey PrivateKey::from_hex(const std::string& hex_str) {
    auto bytes = ::hdar::from_hex(hex_str);
    if (bytes.size() != KEY_SIZE)
        throw std::runtime_error("invalid private key length");
    PrivateKey sk;
    std::memcpy(sk.raw.data(), bytes.data(), KEY_SIZE);
    return sk;
}

PrivateKey PrivateKey::generate() {
    PrivateKey sk;
    // libsodium 64-byte secret key format: [32-byte seed][32-byte public key]
    // crypto_sign_ed25519_seed_keypair writes pk (32 bytes) and sk (64 bytes)
    // We pass pk = sk.raw.data() + 32 (last 32 bytes) and sk = sk.raw.data() (full 64 bytes)
    uint8_t seed[crypto_sign_SEEDBYTES];
    randombytes_buf(seed, sizeof(seed));
    crypto_sign_ed25519_seed_keypair(sk.raw.data() + 32, sk.raw.data(), seed);
    return sk;
}

// ── OwnerKeyPair ──────────────────────────────────────────────

OwnerKeyPair::OwnerKeyPair(const PrivateKey& sk)
    : private_key(sk), public_key(sk.public_key()) {}

OwnerKeyPair OwnerKeyPair::generate() {
    return OwnerKeyPair(PrivateKey::generate());
}

OwnerKeyPair OwnerKeyPair::from_private_hex(const std::string& hex) {
    return OwnerKeyPair(PrivateKey::from_hex(hex));
}

std::string OwnerKeyPair::sign_json(const JsonValue& obj) const {
    return private_key.sign_json(obj);
}

std::string OwnerKeyPair::sign_bytes(const std::vector<uint8_t>& data) const {
    return private_key.sign_hex(data);
}

void OwnerKeyPair::save(const std::string& path) const {
    // Save raw 64-byte private key to file
    std::vector<uint8_t> raw_bytes(private_key.raw.begin(), private_key.raw.end());
    write_bytes_to_file(path, raw_bytes);
    chmod(path.c_str(), 0600);
}

OwnerKeyPair OwnerKeyPair::load(const std::string& path) {
    auto bytes = read_file_to_bytes(path);
    if (bytes.size() != PrivateKey::KEY_SIZE)
        throw std::runtime_error("invalid key file size");
    PrivateKey sk;
    std::memcpy(sk.raw.data(), bytes.data(), PrivateKey::KEY_SIZE);
    return OwnerKeyPair(sk);
}

// ── HostKeyPair ───────────────────────────────────────────────

HostKeyPair HostKeyPair::generate(const std::string& hid) {
    HostKeyPair hkp;
    hkp.private_key = PrivateKey::generate();
    hkp.public_key = hkp.private_key.public_key();
    hkp.host_id = hid;
    return hkp;
}

std::string HostKeyPair::sign_json(const JsonValue& obj) const {
    return private_key.sign_json(obj);
}

std::string HostKeyPair::sign_bytes(const std::vector<uint8_t>& data) const {
    return private_key.sign_hex(data);
}

// ── UUID / token generation ───────────────────────────────────

std::string generate_uuid_hex() {
    uint8_t buf[16];
    randombytes_buf(buf, sizeof(buf));
    // Set version (4) and variant bits
    buf[6] = (buf[6] & 0x0f) | 0x40;
    buf[8] = (buf[8] & 0x3f) | 0x80;
    return to_hex(buf, sizeof(buf));
}

std::string generate_agent_id() {
    return "agent-" + generate_uuid_hex().substr(0, 12);
}

std::string generate_fencing_token() {
    return generate_uuid_hex();
}

// ── File I/O helpers ──────────────────────────────────────────

std::string read_file_to_string(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open file: " + path);
    std::ostringstream oss;
    oss << f.rdbuf();
    return oss.str();
}

std::vector<uint8_t> read_file_to_bytes(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open file: " + path);
    std::vector<uint8_t> bytes(
        (std::istreambuf_iterator<char>(f)),
        std::istreambuf_iterator<char>());
    return bytes;
}

void write_string_to_file(const std::string& path, const std::string& content) {
    std::ofstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot write file: " + path);
    f << content;
}

void write_bytes_to_file(const std::string& path, const std::vector<uint8_t>& data) {
    std::ofstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot write file: " + path);
    f.write(reinterpret_cast<const char*>(data.data()), data.size());
}

// ── Time ──────────────────────────────────────────────────────

double epoch_seconds() {
    auto now = std::chrono::system_clock::now();
    return std::chrono::duration<double>(now.time_since_epoch()).count();
}

} // namespace hdar
