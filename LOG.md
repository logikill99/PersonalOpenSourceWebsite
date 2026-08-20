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
2. Copy the **local-only** sanitized seed (`prod-import/db.seed.sqlite3` on slab, not in git) to `/data/db.sqlite3` on the volume.
3. Set env vars: `SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG=False`, `DATABASE_PATH=/data/db.sqlite3`, plus `DJANGO_SUPERUSER_*` if you want a fresh admin user.
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

## 2026-08-17 — salvage without Wren

Wren iced 2026-08-16. Matt asked to get the website code where it needs to be.
Morgan pushed the local-only modernize tips to origin so they are not hostage
to the hermes-wren sandbox disk:

- `origin/modernize/settings` @ `8174dbd`
- `origin/modernize/django6-deps` @ `fe931b9`
- `origin/modernize/alpine-accordion` @ `976862d`

Then opened `salvage/railway-hardening` from the alpine tip with the leftover
audit fixes. PR #19 (`reconcile/prod-baseline`) is an incomplete intermediate
and should stay closed or be superseded. Do not merge #19 as the deploy PR.

Honest leftover facts:
- `prod-import/db.seed.sqlite3` is local-only. It was never in any git tree.
- Public `main` still tracks `.env` (`7b0fd2b`). History purge is a separate job.
- Railway project exists; nothing is deployed. DNS cutover is not in this PR.

*Log continued by Morgan. Last updated: 2026-08-17.*

## 2026-08-17 later — adversarial fixes

Claude Code BLOCKED deploy on the local seed: contactme tables were missing
while django_migrations said they were applied. Repaired live db.sqlite3 and
the canonical seed at sandboxes/hermes-wren/work/prod-import/db.seed.sqlite3
via migrate contactme zero --fake && migrate contactme.

Also: IP-keyed rate limit after valid posts, blog comment honeypot, 404 for
missing posts, DATABASE_PATH blank-safe, healthcheck SSL exempt + railway
health host, resized 1.jpg 12.8MB -> ~70KB, titles/excerpts/copy, contact CSS.

## 2026-08-20 — Production hardening pass (P0/P1 from the audit)

All P0 and P1 items addressed on `salvage/railway-hardening`. One commit per
logical change; every commit message carries its own adversarial-review notes.
Suite: 40 tests green. `check --deploy --fail-level WARNING`: zero issues.

### Decisions & threat models

- **EMAIL_BACKEND (P0.1):** env override was silently clobbered by a duplicate
  SMTP assignment later in settings.py. Fixed; subprocess regression tests
  cover both the override and the SMTP default.
- **Contact PII (P0.4): email-only, no persistence.** Contact/Message models,
  tables (migration 0003), and admin entries removed. Visitor PII never
  touches the SQLite volume, so there is no retention policy to maintain and
  nothing to leak via backups/admin. On SMTP failure the visitor is told
  delivery failed and their text is preserved in the re-rendered form —
  nothing is silently stored. Threat: DB exfil / backup leak / admin
  compromise exposing visitor PII → eliminated by not storing it.
- **Comments (P0.3): moderation queue.** `Comment.approved` defaults False;
  only approved comments render; admin has a filter + bulk approve action;
  submitters see "awaiting moderation". Pre-existing comments were approved in
  the migration (they were already public). Threat: honeypot/rate-limit bypass
  still cannot publish spam/XSS-bait — a human gate sits in front of render.
- **Media (P0.2): no user media in v1.** Every image is a static asset served
  by WhiteNoise. The unused blog `Image` model (TODO stub, zero rows) was
  removed along with MEDIA_URL/MEDIA_ROOT, the DEBUG-only static() url hook,
  and the pillow dependency. Nothing can 404 behind a DEBUG-only helper in
  prod. Future uploads require a real storage backend, not DEBUG static().
- **Rate limiting (P0.6):** default cache is now DatabaseCache on the SQLite
  volume (`createcachetable` in entrypoint) — shared across gunicorn workers;
  LocMemCache had silently multiplied the limit by the worker count.
  **Proxy trust:** X-Forwarded-For is consulted only when TRUST_PROXY is on,
  and only its RIGHTMOST entry (appended by Railway's edge — the single
  trusted proxy) is used, validated as a real IP, else REMOTE_ADDR.
  TRUST_PROXY=True is only valid when exactly one trusted proxy fronts the
  app; with no proxy it must stay off or XFF becomes client-controlled.
  Known accepted race: the read-modify-write window can admit ~1 extra post;
  that is bounded noise, unlike the old per-worker multiplication.
- **Docker (P0.5):** entrypoint starts as root only to chown the root-owned
  Railway volume mount, then unconditionally drops to appuser (uid 10001) via
  su-exec — deploy gate, migrations, and gunicorn (incl. PID 1) all run
  unprivileged. `/app` stays root-owned (running code cannot modify itself);
  bytecode precompiled at build. A bare USER directive was rejected because
  it cannot fix root-owned volume mounts.
- **Headers + CSP (P1.7/8):** nosniff, Referrer-Policy
  strict-origin-when-cross-origin, X-Frame-Options DENY, HttpOnly +
  SameSite=Lax cookies. Enforced CSP via Django 6's native middleware:
  default-src 'self'; script-src 'self' + pinned/SRI jsdelivr Alpine +
  'unsafe-eval' (standard Alpine build compiles x-data with new Function();
  inline <script> stays blocked, which is what matters given post bodies
  render with |safe); object-src/frame-ancestors 'none'; form-action 'self'.
- **Logging (P1.9):** single console handler to stdout, INFO default,
  LOG_LEVEL env override; gunicorn access/error logs to '-'.
- **Release gate (P1.10):** entrypoint runs
  `manage.py check --deploy --fail-level WARNING` before migrating — a
  misconfigured image refuses to boot. SECURE_HSTS_PRELOAD now defaults True
  (header only = preload-list *eligibility*; nothing auto-submitted;
  SECURE_HSTS_PRELOAD=False opts out).
- **Admin (P1.11):** stays at /admin/. Optional ADMIN_IP_ALLOWLIST
  (IPs/CIDRs) 404s everyone else; invalid entries refuse to boot. Admin login
  POSTs share the DB-backed limiter (3/min/IP → 429) so the exposed form
  cannot be brute-forced at speed. Unset allowlist = open admin is the
  documented default posture; recommend setting it once Matt's IPs are known.
- **Git hygiene (P1.12):** no `.env` or sqlite files tracked on this branch
  (`git ls-files` verified); .gitignore/.dockerignore already cover them.
  Public `main` still has `.env` in *history* (7b0fd2b) — the purge remains a
  separate task and any secrets in it must be considered burned/rotated.

### Verification (browser + curl + Docker, all against the built image)

- `curl -I`: CSP exact, nosniff, DENY, Referrer-Policy present on every page;
  HSTS (max-age=31536000; includeSubDomains; preload) on forwarded-HTTPS.
- Headless Chrome on /about under the *enforced* CSP: 97 Alpine components
  initialized, 0 x-cloak left, no CSP violations; admin login renders.
- Contact flow with real CSRF: 3 posts OK → 4th blocked, even while rotating
  spoofed X-Forwarded-For each request. Comment posted live → 302 but body
  absent from public page (held for moderation).
- Docker: PID 1 = appuser; volume db owned 10001; `touch /app/evil` denied;
  `su-exec root` as appuser → EPERM; cache round-trip across two separate
  processes proves shared limiter; SECURE_SSL_REDIRECT=False boot refused by
  the gate; ADMIN_IP_ALLOWLIST=banana → workers refuse to boot;
  allowlist=203.0.113.7 → /admin/ 404, public pages 200; plain HTTP 301s to
  HTTPS; /health/ 200; superuser created from env on first boot.

### Open items / notes for Matt

- Set `ADMIN_IP_ALLOWLIST` in Railway once your stable IPs are known
  (optional but recommended).
- `main` history still contains the old `.env` — schedule the history purge
  and rotate anything that was in it.
- Approve/deny held comments at /admin/blog/comment/ (filter: unapproved).

*Hardening pass by Claude (fable) under AGENTS.md, 2026-08-20.*
