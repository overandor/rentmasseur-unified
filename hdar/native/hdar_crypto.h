// hdar_crypto.h — Ed25519 cryptographic kernel for HDAR continuity.
// Native macOS implementation using Apple CryptoKit.
//
// The owner holds an Ed25519 private key. Hosts receive only the public key.
// Hosts generate ephemeral Ed25519 key pairs for execution-witness receipts.
// A host can verify owner signatures but cannot forge them.

#ifndef HDAR_CRYPTO_H
#define HDAR_CRYPTO_H

#include <string>
#include <vector>
#include <cstdint>
#include <memory>

namespace hdar {

// ─── SHA-256 ───────────────────────────────────────────────────────────

/// Compute SHA-256 of data, return hex string (64 chars).
std::string sha256_hex(const uint8_t* data, size_t len);
std::string sha256_hex(const std::string& data);
std::string sha256_hex(const std::vector<uint8_t>& data);

/// Compute SHA-256 of a file, return hex string.
std::string sha256_file(const std::string& path);

// ─── Ed25519 Key Pair ──────────────────────────────────────────────────

/// Ed25519 private key (32 bytes) + public key (32 bytes).
struct Ed25519KeyPair {
    std::vector<uint8_t> private_key;  // 32 bytes
    std::vector<uint8_t> public_key;   // 32 bytes

    std::string public_key_hex() const;
    std::string private_key_hex() const;

    static Ed25519KeyPair generate();
    static Ed25519KeyPair from_private_hex(const std::string& hex);
    static Ed25519KeyPair from_private_bytes(const uint8_t* raw, size_t len);
};

/// Ed25519 public key only (for verification).
struct Ed25519PublicKey {
    std::vector<uint8_t> key;  // 32 bytes

    std::string hex() const;
    static Ed25519PublicKey from_hex(const std::string& hex);
    static Ed25519PublicKey from_bytes(const uint8_t* raw, size_t len);
};

// ─── Signing and Verification ──────────────────────────────────────────

/// Sign data with Ed25519 private key. Returns 64-byte signature.
std::vector<uint8_t> ed25519_sign(
    const Ed25519KeyPair& key,
    const uint8_t* data, size_t len
);

/// Sign a string.
std::vector<uint8_t> ed25519_sign(
    const Ed25519KeyPair& key,
    const std::string& data
);

/// Verify an Ed25519 signature. Returns true if valid.
bool ed25519_verify(
    const Ed25519PublicKey& pub,
    const uint8_t* data, size_t data_len,
    const uint8_t* sig, size_t sig_len
);

/// Verify with hex-encoded signature.
bool ed25519_verify_hex(
    const Ed25519PublicKey& pub,
    const std::string& data,
    const std::string& sig_hex
);

/// Convert bytes to hex string.
std::string to_hex(const uint8_t* data, size_t len);
std::string to_hex(const std::vector<uint8_t>& data);

/// Convert hex string to bytes.
std::vector<uint8_t> from_hex(const std::string& hex);

} // namespace hdar

#endif // HDAR_CRYPTO_H
