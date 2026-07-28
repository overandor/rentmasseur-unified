# Workflows

`ci.yml` intentionally checks out without Git LFS smudging so unavailable generated binaries cannot block validation. It builds a fresh deterministic SQLite database on every run and publishes the verified database as a short-lived artifact.
