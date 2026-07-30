# CI database seeding

Run locally with:

```bash
python scripts/ci_seed_db.py --rows 50 --db artifacts/ci/rentmasseur_ci.sqlite3
```

The command is deterministic for lead and receipt data, recreates the seed tables on each run, enables foreign keys, and fails when SQLite integrity or expected row counts do not pass.
