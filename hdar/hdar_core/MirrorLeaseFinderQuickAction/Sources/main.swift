import AppKit
import CryptoKit
import Foundation
import Security

private let keychainService = "com.mirrorlease.device-signing-key"
private let keychainAccount = "device-ed25519-v1"
private let leaseHours: Double = 72

enum MirrorLeaseError: LocalizedError {
    case noFiles
    case keyDeclined
    case keychain(OSStatus)
    case clipboard
    case invalidInput

    var errorDescription: String? {
        switch self {
        case .noFiles: return "Select at least one regular file in Finder."
        case .keyDeclined: return "Device signing-key creation was cancelled."
        case .keychain(let status): return "macOS Keychain error: \(status)"
        case .clipboard: return "The invitation could not be placed on the clipboard."
        case .invalidInput: return "MirrorLease received an invalid protocol request."
        }
    }
}

struct LocalFileRecord {
    let citizenID: String
    let path: String
    let contentHash: String
    let size: Int64

    var dictionary: [String: Any] {
        [
            "citizen_id": citizenID,
            "local_path": path,
            "content_hash": contentHash,
            "size": size,
        ]
    }
}

@main
struct MirrorLeaseQuickShare {
    static func main() {
        NSApplication.shared.setActivationPolicy(.accessory)
        do {
            let arguments = CommandLine.arguments
            if arguments.dropFirst().first == "--sign-stdin" {
                try signStandardInput()
                return
            }
            if arguments.dropFirst().first == "--approve-stdin" {
                try approveStandardInput()
                return
            }
            let files = try selectedFiles(Array(arguments[1...]))
            let key = try loadOrCreateDeviceKey()
            let invitation = try createInvitation(files: files, key: key)
            try copyToClipboard(invitation.text)
            showCompletion(mailboxID: invitation.mailboxID, fileCount: files.count)
        } catch MirrorLeaseError.keyDeclined {
            return
        } catch {
            showError(error.localizedDescription)
            exit(1)
        }
    }

    static func signStandardInput() throws {
        let input = FileHandle.standardInput.readDataToEndOfFile()
        guard !input.isEmpty else { throw MirrorLeaseError.invalidInput }
        let key = try loadOrCreateDeviceKey()
        let result: [String: Any] = [
            "issuer_public_key": key.publicKey.rawRepresentation.hex,
            "issuer_fingerprint": String(sha256Hex(key.publicKey.rawRepresentation).prefix(16)),
            "signature": try key.signature(for: input).hex,
        ]
        FileHandle.standardOutput.write(try canonicalJSON(result))
    }

    static func approveStandardInput() throws {
        let input = FileHandle.standardInput.readDataToEndOfFile()
        guard let request = try JSONSerialization.jsonObject(with: input) as? [String: Any] else {
            throw MirrorLeaseError.invalidInput
        }
        let operation = String(describing: request["operation"] ?? "access")
        let agent = String(describing: request["agent_id"] ?? "unknown agent")
        let transport = String(describing: request["transport"] ?? "unknown transport")
        let citizen = String(describing: request["citizen_id"] ?? "selected file")

        NSApplication.shared.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "Allow this MirrorLease request?"
        alert.informativeText = "\(agent) requests \(operation) on \(citizen) through \(transport). The request is still limited by the signed lease and its expiration."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Allow once")
        alert.addButton(withTitle: "Deny")
        let approved = alert.runModal() == .alertFirstButtonReturn
        FileHandle.standardOutput.write(try canonicalJSON(["approved": approved]))
    }

    static func selectedFiles(_ arguments: [String]) throws -> [URL] {
        let manager = FileManager.default
        let files = arguments.compactMap { argument -> URL? in
            let url = URL(fileURLWithPath: argument).standardizedFileURL
            var isDirectory: ObjCBool = false
            guard manager.fileExists(atPath: url.path, isDirectory: &isDirectory), !isDirectory.boolValue else {
                return nil
            }
            return url
        }
        guard !files.isEmpty else { throw MirrorLeaseError.noFiles }
        return files
    }

    static func loadOrCreateDeviceKey() throws -> Curve25519.Signing.PrivateKey {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecSuccess, let data = result as? Data {
            return try Curve25519.Signing.PrivateKey(rawRepresentation: data)
        }
        guard status == errSecItemNotFound else { throw MirrorLeaseError.keychain(status) }
        guard approveKeyCreation() else { throw MirrorLeaseError.keyDeclined }

        let key = Curve25519.Signing.PrivateKey()
        let add: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
            kSecAttrLabel as String: "MirrorLease device signing key",
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
            kSecValueData as String: key.rawRepresentation,
        ]
        let addStatus = SecItemAdd(add as CFDictionary, nil)
        guard addStatus == errSecSuccess else { throw MirrorLeaseError.keychain(addStatus) }
        return key
    }

    static func approveKeyCreation() -> Bool {
        NSApplication.shared.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "Create MirrorLease device identity?"
        alert.informativeText = "The private Ed25519 signing key will be stored in macOS Keychain. It will never be placed on the clipboard or included in an invitation."
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Create in Keychain")
        alert.addButton(withTitle: "Cancel")
        return alert.runModal() == .alertFirstButtonReturn
    }

    static func createInvitation(
        files: [URL],
        key: Curve25519.Signing.PrivateKey
    ) throws -> (text: String, mailboxID: String) {
        let now = Date().timeIntervalSince1970
        let expires = now + leaseHours * 3600
        let invitationID = randomHex(bytes: 16)
        let mailboxID = "mirror-\(randomHex(bytes: 6))"
        let token = randomHex(bytes: 32)
        let challenge = randomHex(bytes: 16)
        let publicKey = key.publicKey.rawRepresentation
        let fingerprint = sha256Hex(publicKey).prefix(16)

        var localFiles: [LocalFileRecord] = []
        var grants: [String: [String]] = [:]
        for file in files {
            let values = try file.resourceValues(forKeys: [.fileSizeKey])
            let digest = try hashFile(file)
            let citizenID = "file-\(digest.prefix(16))"
            localFiles.append(LocalFileRecord(
                citizenID: citizenID,
                path: file.path,
                contentHash: digest,
                size: Int64(values.fileSize ?? 0)
            ))
            grants[citizenID] = ["read", "summarize", "verify_hash"]
        }

        let signedClaims: [String: Any] = [
            "invitation_id": invitationID,
            "mailbox_id": mailboxID,
            "token_hash": sha256Hex(Data(token.utf8)),
            "task_description": "Review the selected local file through MirrorLease",
            "recipient_id": "",
            "conversation_label": "",
            "challenge": challenge,
            "grants": grants,
            "created_at": now,
            "expires_at": expires,
            "issuer_fingerprint": String(fingerprint),
        ]
        let canonicalClaims = try canonicalJSON(signedClaims)
        let signature = try key.signature(for: canonicalClaims).hex

        let publicPayload: [String: Any] = [
            "invitation_id": invitationID,
            "mailbox_id": mailboxID,
            "token": token,
            "task": "Review the selected local file through MirrorLease",
            "recipient_id": "",
            "conversation_label": "",
            "challenge": challenge,
            "grants": grants,
            "created_at": now,
            "expires_at": expires,
            "issuer_public_key": publicKey.hex,
            "issuer_fingerprint": String(fingerprint),
            "lease_signature": signature,
        ]
        let encoded = try canonicalJSON(publicPayload).base64URLEncodedString()
        let invitationText = "mirrorlease:v1:\(encoded)"

        let privateRecord: [String: Any] = [
            "version": 1,
            "invitation_id": invitationID,
            "mailbox_id": mailboxID,
            "state": "waiting",
            "created_at": now,
            "expires_at": expires,
            "token_hash": sha256Hex(Data(token.utf8)),
            "challenge": challenge,
            "grants": grants,
            "issuer_public_key": publicKey.hex,
            "issuer_fingerprint": String(fingerprint),
            "lease_signature": signature,
            "private_files": localFiles.map(\.dictionary),
        ]
        try persistPrivateRecord(privateRecord, invitationID: invitationID)
        return (invitationText, mailboxID)
    }

    static func hashFile(_ url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            let data = try handle.read(upToCount: 1024 * 1024) ?? Data()
            if data.isEmpty { break }
            hasher.update(data: data)
        }
        return Data(hasher.finalize()).hex
    }

    static func persistPrivateRecord(_ record: [String: Any], invitationID: String) throws {
        let manager = FileManager.default
        let root = manager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("MirrorLease", isDirectory: true)
        let leases = root.appendingPathComponent("leases", isDirectory: true)
        try manager.createDirectory(at: leases, withIntermediateDirectories: true)
        try manager.setAttributes([.posixPermissions: 0o700], ofItemAtPath: root.path)
        try manager.setAttributes([.posixPermissions: 0o700], ofItemAtPath: leases.path)
        let destination = leases.appendingPathComponent("\(invitationID).json")
        try canonicalJSON(record).write(to: destination, options: .atomic)
        try manager.setAttributes([.posixPermissions: 0o600], ofItemAtPath: destination.path)
    }

    static func copyToClipboard(_ invitation: String) throws {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        guard pasteboard.setString(invitation, forType: .string) else {
            throw MirrorLeaseError.clipboard
        }
    }

    static func showCompletion(mailboxID: String, fileCount: Int) {
        NSApplication.shared.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "MirrorLease invitation copied"
        alert.informativeText = "\(fileCount) file\(fileCount == 1 ? "" : "s") leased through \(mailboxID) for 72 hours. Paste the invitation into the approved AI session."
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Done")
        alert.runModal()
    }

    static func showError(_ message: String) {
        NSApplication.shared.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "MirrorLease could not create the invitation"
        alert.informativeText = message
        alert.alertStyle = .critical
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }

    static func canonicalJSON(_ object: Any) throws -> Data {
        try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys, .withoutEscapingSlashes])
    }

    static func randomHex(bytes count: Int) -> String {
        var bytes = [UInt8](repeating: 0, count: count)
        precondition(SecRandomCopyBytes(kSecRandomDefault, count, &bytes) == errSecSuccess)
        return Data(bytes).hex
    }

    static func sha256Hex(_ data: Data) -> String {
        Data(SHA256.hash(data: data)).hex
    }
}

private extension Data {
    var hex: String { map { String(format: "%02x", $0) }.joined() }

    func base64URLEncodedString() -> String {
        base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
