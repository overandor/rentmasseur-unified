// hdar_crypto.mm — Ed25519 cryptographic kernel using OpenSSL 3.x.
// Native macOS implementation. No Python. No mocks. No Swift required.

#include "hdar_crypto.h"
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <openssl/rand.h>
#include <fstream>
#include <sstream>
#include <cstring>

namespace hdar {

// ─── Hex helpers ───────────────────────────────────────────────────────

std::string to_hex(const uint8_t* data, size_t len) {
    static const char hex[] = "0123456789abcdef";
    std::string out;
    out.reserve(len * 2);
    for (size_t i = 0; i < len; i++) {
        out.push_back(hex[(data[i] >> 4) & 0xF]);
        out.push_back(hex[data[i] & 0xF]);
    }
    return out;
}

std::string to_hex(const std::vector<uint8_t>& data) {
    return to_hex(data.data(), data.size());
}

std::vector<uint8_t> from_hex(const std::string& hex) {
    std::vector<uint8_t> out;
    out.reserve(hex.size() / 2);
    for (size_t i = 0; i + 1 < hex.size(); i += 2) {
        auto nib = [](char c) -> int {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            if (c >= 'A' && c <= 'F') return c - 'A' + 10;
            return 0;
        };
        out.push_back((nib(hex[i]) << 4) | nib(hex[i + 1]));
    }
    return out;
}

// ─── SHA-256 ───────────────────────────────────────────────────────────

std::string sha256_hex(const uint8_t* data, size_t len) {
    uint8_t digest[SHA256_DIGEST_LENGTH];
    SHA256(data, len, digest);
    return to_hex(digest, SHA256_DIGEST_LENGTH);
}

std::string sha256_hex(const std::string& data) {
    return sha256_hex((const uint8_t*)data.data(), data.size());
}

std::string sha256_hex(const std::vector<uint8_t>& data) {
    return sha256_hex(data.data(), data.size());
}

std::string sha256_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    return sha256_hex((const uint8_t*)content.data(), content.size());
}

// ─── Ed25519 Key Pair ──────────────────────────────────────────────────

std::string Ed25519KeyPair::public_key_hex() const {
    return to_hex(public_key);
}

std::string Ed25519KeyPair::private_key_hex() const {
    return to_hex(private_key);
}

Ed25519KeyPair Ed25519KeyPair::generate() {
    EVP_PKEY* pkey = EVP_PKEY_Q_keygen(NULL, NULL, "ED25519");
    if (!pkey) return {};

    Ed25519KeyPair kp;

    size_t pub_len = 32;
    kp.public_key.resize(pub_len);
    EVP_PKEY_get_raw_public_key(pkey, kp.public_key.data(), &pub_len);
    kp.public_key.resize(pub_len);

    size_t priv_len = 32;
    kp.private_key.resize(priv_len);
    EVP_PKEY_get_raw_private_key(pkey, kp.private_key.data(), &priv_len);
    kp.private_key.resize(priv_len);

    EVP_PKEY_free(pkey);
    return kp;
}

Ed25519KeyPair Ed25519KeyPair::from_private_hex(const std::string& hex) {
    auto raw = from_hex(hex);
    return from_private_bytes(raw.data(), raw.size());
}

Ed25519KeyPair Ed25519KeyPair::from_private_bytes(const uint8_t* raw, size_t len) {
    Ed25519KeyPair kp;
    kp.private_key.assign(raw, raw + len);

    EVP_PKEY* pkey = EVP_PKEY_new_raw_private_key(EVP_PKEY_ED25519, NULL, raw, len);
    if (!pkey) return {};

    size_t pub_len = 32;
    kp.public_key.resize(pub_len);
    EVP_PKEY_get_raw_public_key(pkey, kp.public_key.data(), &pub_len);
    kp.public_key.resize(pub_len);

    EVP_PKEY_free(pkey);
    return kp;
}

// ─── Ed25519 Public Key ────────────────────────────────────────────────

std::string Ed25519PublicKey::hex() const {
    return to_hex(key);
}

Ed25519PublicKey Ed25519PublicKey::from_hex(const std::string& hex) {
    auto raw = from_hex(hex);
    Ed25519PublicKey pk;
    pk.key = raw;
    return pk;
}

Ed25519PublicKey Ed25519PublicKey::from_bytes(const uint8_t* raw, size_t len) {
    Ed25519PublicKey pk;
    pk.key.assign(raw, raw + len);
    return pk;
}

// ─── Signing and Verification ──────────────────────────────────────────

std::vector<uint8_t> ed25519_sign(const Ed25519KeyPair& key, const uint8_t* data, size_t len) {
    EVP_PKEY* pkey = EVP_PKEY_new_raw_private_key(EVP_PKEY_ED25519, NULL,
                                                   key.private_key.data(), key.private_key.size());
    if (!pkey) return {};

    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    size_t sig_len = 64;
    std::vector<uint8_t> sig(sig_len);

    EVP_DigestSignInit(ctx, NULL, NULL, NULL, pkey);
    EVP_DigestSign(ctx, sig.data(), &sig_len, data, len);
    sig.resize(sig_len);

    EVP_MD_CTX_free(ctx);
    EVP_PKEY_free(pkey);
    return sig;
}

std::vector<uint8_t> ed25519_sign(const Ed25519KeyPair& key, const std::string& data) {
    return ed25519_sign(key, (const uint8_t*)data.data(), data.size());
}

bool ed25519_verify(const Ed25519PublicKey& pub, const uint8_t* data, size_t data_len,
                     const uint8_t* sig, size_t sig_len) {
    EVP_PKEY* pkey = EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519, NULL,
                                                  pub.key.data(), pub.key.size());
    if (!pkey) return false;

    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    int rc = EVP_DigestVerifyInit(ctx, NULL, NULL, NULL, pkey);
    if (rc != 1) { EVP_MD_CTX_free(ctx); EVP_PKEY_free(pkey); return false; }

    rc = EVP_DigestVerify(ctx, sig, sig_len, data, data_len);

    EVP_MD_CTX_free(ctx);
    EVP_PKEY_free(pkey);
    return rc == 1;
}

bool ed25519_verify_hex(const Ed25519PublicKey& pub, const std::string& data, const std::string& sig_hex) {
    auto sig = from_hex(sig_hex);
    return ed25519_verify(pub, (const uint8_t*)data.data(), data.size(), sig.data(), sig.size());
}

} // namespace hdar
