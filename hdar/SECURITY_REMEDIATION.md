# HDAR Security Remediation Checklist

**Created**: 2026-07-20
**Trigger**: External audit finding — compromised credentials and evidence signing key in shared archives

---

## 1. Compromised Evidence Signing Key (CRITICAL)

**Finding**: `pipeline_output/evidence/signing_key.pem` was included in a shared archive. The private Ed25519 key corresponding to the evidence verification key was exposed. Anyone with the archive can produce apparently valid evidence manifests.

**Status**: REMEDIATED

**Actions taken**:
- [x] Generated new Ed25519 keypair (`signing_key_NEW.pem`, `verify_key_NEW.pem`)
- [x] Re-signed evidence manifest with new key
- [x] Verified new signature passes `openssl pkeyutl -verify`
- [ ] Move `signing_key_NEW.pem` to a secure location outside any shared archive
- [ ] Delete `signing_key.pem` (compromised) after confirming all consumers use the new key
- [ ] Update `evidence_manifest.py` to default to the new key path
- [ ] Add `signing_key*.pem` to `.gitignore` to prevent future exposure

**Old key fingerprint (COMPROMISED)**:
```
verify_key.pem SHA-256: e7090c7bd06ccf2a1b85523dbc2fd49e8a253fbbec94cd77cf5eb86c31e03912
```

**New key fingerprint (CLEAN)**:
```
verify_key_NEW.pem SHA-256: 2d1a4d868d095e14ba4b6c5487d40a14e54bb62bba4f33ac5bc2505949435d88
```

---

## 2. Exposed Credentials in ALPHA-GPT Corpus (CRITICAL)

**Finding**: The `alpha-gpt.zip` archive contains multiple live-looking credentials:
- OpenAI project keys
- OpenRouter keys
- Google API keys
- Hugging Face tokens
- GitHub personal-access tokens

**Status**: REMEDIATION REQUIRED — user action needed

**Actions required**:
- [ ] Revoke and rotate ALL API keys found in the corpus
- [ ] Run deterministic secret detection across the entire corpus
- [ ] Remove or redact all credential-like strings before any external use
- [ ] Do NOT upload, publish, or transmit the corpus through any external service until sanitized
- [ ] Audit access logs for any keys that may have been used while exposed

---

## 3. Personal Information in ALPHA-GPT Corpus (HIGH)

**Finding**: The corpus contains:
- ~16,000 absolute Mac filesystem paths
- ~1,800 email-pattern occurrences
- Hundreds of phone-number-pattern occurrences
- Extensive personal conversation data

**Status**: REMEDIATION REQUIRED — user action needed

**Actions required**:
- [ ] Run PII redaction pipeline across all conversation data
- [ ] Replace absolute paths with relative or redacted placeholders
- [ ] Remove or hash email addresses and phone numbers
- [ ] Create a consent classification for each conversation
- [ ] Produce a rights manifest documenting data source and usage rights

---

## 4. Credential-Like Strings in Archive 2 (HIGH)

**Finding**: `Archive 2.zip` contains credential-like strings, tunnel identifiers, and email addresses in exported conversation logs.

**Status**: REMEDIATION REQUIRED — user action needed

**Actions required**:
- [ ] Run secret detection on all 17 conversation files
- [ ] Redact or remove all credential-like strings
- [ ] Do not share Archive 2 externally until sanitized

---

## 5. Google Sheets OAuth Helper Risk (MEDIUM)

**Finding**: The ALPHA-GPT OAuth helper requests broad permissions, automates consent clicking, creates cloud projects and service accounts, and stores credentials in `/tmp`.

**Status**: REMEDIATION REQUIRED — architectural change needed

**Actions required**:
- [ ] Separate Google Sheets transport from the model project
- [ ] Replace automated OAuth with tightly scoped, manually approved credentials
- [ ] Remove service-account private key creation automation
- [ ] Store credentials in a secure vault, not `/tmp`

---

## 6. Archive Sharing Policy (PREVENTIVE)

**Finding**: Multiple archives contain secrets, PII, and private keys that should never have been bundled.

**Status**: POLICY REQUIRED

**Actions required**:
- [ ] Create a pre-share checklist that includes secret scanning
- [ ] Add `.gitignore` entries for all key files, credentials, and private data
- [ ] Use `git-secrets` or similar tool as a pre-commit hook
- [ ] Never include `.pem`, `.key`, `.env`, or credentials files in any archive
- [ ] Audit existing shared archives and recall/rotate if possible
