# CI database artifact

The `CI` GitHub Actions workflow creates `rentmasseur_ci.sqlite3` here at runtime, verifies its integrity and seeded row counts, then uploads it as a workflow artifact. Generated database files are intentionally not committed.
