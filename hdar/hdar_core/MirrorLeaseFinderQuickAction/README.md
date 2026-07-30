# MirrorLease Finder Quick Action

Select one or more files in Finder, right-click, and choose the top-level
**Share with AI — MirrorLease** item. No Quick Actions submenu is required. The action:

1. hashes the selected files locally;
2. creates a device-signed 72-hour lease with `read`, `summarize`, and
   `verify_hash` grants;
3. stores private path mappings in `~/Library/Application Support/MirrorLease`;
4. puts only the public invitation on the clipboard.

On first use, MirrorLease asks before creating the Ed25519 device signing key
in macOS Keychain. Base64url is transport encoding, not encryption.
