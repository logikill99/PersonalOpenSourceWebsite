# Migration & Modernization Log

## RECONCILE PROPOSAL — Final Decisions (Matt, 2026-08-10)

### Contacts / PII: **STRIP**
- All `contactme_*` tables were dropped from the sanitized seed (`prod-import/db.seed.sqlite3`).
- The original production backup remains at `prod-import/db.sqlite3.original` if data recovery is ever needed.
- Ratified by Matt via Morgan, 2026-08-10 22:57 UTC.

### Superuser: **OPTION B — Fresh via Environment**
- The existing `logikill99` superuser hash was **removed** from `db.seed.sqlite3`.
- A fresh superuser is created at deploy time via `DJANGO_SUPERUSER_*` environment variables.
- The `entrypoint.sh` already handles this idempotently: it runs `createsuperuser --noinput` only when `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD` are set.
- **Do not** carry any production password hash into the seed or repo.

### Seed DB State (as of 2026-08-10)
- **Path:** `prod-import/db.seed.sqlite3`
- **Contact tables:** none (dropped)
- **auth_user:** 0 rows (superuser stripped)
- **Content preserved:** blog posts (2), categories (1), skills (39), experiences (8), experience-skill links (58), Django permissions/content types/migrations
- **Backup of pre-strip seed:** `prod-import/db.seed.sqlite3.pre-superuser-strip`

### Deploy Checklist
1. Mount Railway volume at `/data`.
2. Copy `prod-import/db.seed.sqlite3` to `/data/db.sqlite3` on the volume.
3. Set env vars: `DATABASE_PATH=/data/db.sqlite3`, `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`, `DJANGO_SUPERUSER_EMAIL`.
4. Redeploy. `entrypoint.sh` will run migrations and create the superuser if credentials are present.

---

## Active Branch Stack

| Branch | Head | Purpose |
|--------|------|---------|
| `main` | `471fdad` | Upstream sync |
| `reconcile/prod-baseline` | `2a2f5f5` | Production baseline + docs |
| `modernize/settings` | `1bad145` | Hardened settings.py |
| `modernize/django6-deps` | `cfb9284` | Django 6.0.8 dependency bump |
| `modernize/alpine-accordion` | `9a2ec08` | jQuery → Alpine.js refactor |

---

## Completed Work

- **t_118d194a** (2026-08-10): Dispatcher pileup cleanup. Deleted 3 stray branches, removed stale worktree, reset `main` to `origin/main`.
- **t_0ab035cd** (2026-08-10): README updated with SQLite content storage, mslevin.dev, May 2026 last prod activity, PythonAnywhere offline.
- **t_c235f879** (2026-08-10): `.env.example` verified with 17 required keys, 100% coverage against `settings.py`.
- **t_14fc96cb** (2026-08-06): `settings.py` hardened — `env_bool()`, `env_list()`, fail-fast `SECRET_KEY`.
- **t_9574c27e** (2026-08-06): jQuery CDN replaced with Alpine.js v3.14.8 in base templates.

---

*Log maintained by Wren. Last updated: 2026-08-10.*
