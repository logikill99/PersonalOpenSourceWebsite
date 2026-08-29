# Modernization Plan: Django 6 Upgrade + jQuery→Alpine Refactor

**Repo:** logikill99/PersonalOpenSourceWebsite
**Author:** Wren (kanban t_584694b0)
**Date:** 2026-08-06
**Status:** Proposal — pending Morgan review before execution
**Reviewers:** Morgan (senior review), Matt (final approval)

This document synthesizes three audits into one execution plan:

1. **Settings/model cleanup audit** (t_47b9b79f) — settings.py env handling, dead model removal
2. **Django 5.1.3 → 6 deprecation audit** (t_56d98bb7) — full report: `docs/audits/django-6-audit.md`
3. **jQuery → Alpine inventory** (t_ef37ad83) — full report: `docs/audits/jquery-to-alpine-inventory.md`

Each finding below is traceable to a verified audit. Nothing here is vibes.

---

## 1. Executive Summary

The codebase is small, modern, and vanilla Django. The project code itself needs **zero changes** for Django 6 — all removals in 5.2/6.0/6.1 were explicitly searched for and are unused. The work is:

- **1 dependency blocker** (django-phonenumber-field 8.0.0 lacks Django 6 support)
- **1 version floor** (asgiref 3.8.1 < Django 6.0 minimum 3.9.1)
- **1 Python floor** (local dev venv is 3.11; Django 6 requires ≥3.12. Dockerfile already on 3.13 — OK)
- **4 broken/missing settings** (DEBUG bool parsing, ALLOWED_HOSTS CSV, STATIC_ROOT/WhiteNoise, MEDIA_ROOT)
- **1 dead model** (home.MyModel — empty, unreferenced, empty table in prod)
- **1 trivial JS migration** (one 13-line jQuery file → one Alpine component)

**Total estimated effort: ~2 hours** including validation and smoke tests.

### Already in flight (do not duplicate)

| Work | Branch / state | Task |
|------|----------------|------|
| Dependency bump 5.1.3 → 6.0.8 (all pins re-resolved, `manage.py check` passes) | `modernize/django6-deps` @ 4ead0d1 | t_4afc97e2 |
| Alpine CDN swap in base.html + drop jQuery script tags | committed on `reconcile/prod-baseline` @ 3753ea0 | t_9574c27e |
| expand.js behavior port to Alpine | pending | t_830e9eb6 |
| Prod DB reconciliation (orphan blog categories purged, contactme tables dropped, superuser hash stripped, sanitized seed exported to prod-import/db.seed.sqlite3; Matt ratified 2026-08-10) | seed ready, volume setup pending | t_7c2903da, t_10e3a842, t_80379e90 |

---

## 2. Settings & Model Cleanup (from t_47b9b79f)

All findings verified against `reconcile/prod-baseline` @ 471fdad.

### 2.1 DEBUG boolean parsing — BROKEN

- `settings.py:31`: `DEBUG = bool(env('DEBUG'))`
- `bool('False')` → `True`. Any non-empty string is truthy. A prod `.env` with `DEBUG=False` runs with **DEBUG on**.
- **Fix:** `DEBUG = env('DEBUG', 'False').lower() in ('true', '1', 'yes')`

### 2.2 ALLOWED_HOSTS CSV splitting — BROKEN

- `settings.py:66`: `ALLOWED_HOSTS = [str(env('ALLOWED_HOSTS'))]`
- Wraps the raw string in a list → `['localhost,127.0.0.1']` as a single host. With the env var unset it evaluates to `['None']`.
- **Fix:** `ALLOWED_HOSTS = [h.strip() for h in env('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]`

### 2.3 STATIC_ROOT / WhiteNoise — MISSING

- `STATIC_URL` exists but `STATIC_ROOT` is undefined; `whitenoise==6.9.0` is in requirements but its middleware is absent from `MIDDLEWARE`.
- **Fix:** add `STATIC_ROOT = BASE_DIR / 'staticfiles'`; insert `WhiteNoiseMiddleware` after `SecurityMiddleware`; configure `STORAGES['staticfiles']['BACKEND'] = 'whitenoise.storage.CompressedManifestStaticFilesStorage'`.
- **Status:** partially implemented in an uncommitted working tree (settings.py hunk + `whitenoise`/`gunicorn` in requirements). Needs DEBUG/ALLOWED_HOSTS fixes added, then commit as `modernize/settings`.

### 2.4 MEDIA_ROOT — MISSING

- Neither `MEDIA_ROOT` nor `MEDIA_URL` defined. No current upload fields, but blog/contactme will break the day an ImageField appears.
- **Fix:** `MEDIA_ROOT = BASE_DIR / 'media'`, `MEDIA_URL = '/media/'`. (Also present in the uncommitted working tree.)

### 2.5 SECRET_KEY and other env vars — FRAGILE

- `str(env('SECRET_KEY'))` yields the string `'None'` when unset. The app boots with garbage instead of failing fast.
- **Fix:** fail-fast validation for required vars (`SECRET_KEY`, email credentials in prod) via `ImproperlyConfigured`, or explicit defaults where safe. (A fuller hardened settings.py exists in stash@{0}, labeled "wip: modernize/django6-deps pre-t_9574c27e" — review and salvage during implementation.)

### 2.6 Dead model home.MyModel — REMOVE

- Empty `pass` model (`home/models.py:5-6`). Referenced only by its own initial migration. Zero code references anywhere. Table `home_mymodel` exists in prod but has **0 rows**.
- **Removal plan:**
  1. Delete the class from `home/models.py`
  2. `python manage.py makemigrations home --name delete_mymodel` (generates `DeleteModel`)
  3. Back up prod DB, then `python manage.py migrate home`
- **Risk:** none (empty table, no references).

---

## 3. Django 5.1.3 → 6.0 Upgrade (from t_56d98bb7)

Full audit: `docs/audits/django-6-audit.md`. Verdict: project code is clean — every 5.2/6.0/6.1 removal was grep-verified unused. Four issues total:

### 3.1 BLOCKER: django-phonenumber-field 8.0.0

Predates Django 6 (Django 6 support landed in 8.4/8.5). Used in contactme models/forms and INSTALLED_APPS.
**Fix:** → 8.5.0. Also float `phonenumbers` 8.13.49 → 9.x (data-only library).

### 3.2 HIGH: asgiref 3.8.1 below floor

Django 6.0 requires asgiref ≥ 3.9.1.
**Fix:** → `asgiref>=3.9.1` (or unpin; Django declares its own floor).

### 3.3 HIGH: Python ≥ 3.12 floor

Dockerfile is already `python:3.13.0-alpine` (OK). The local `.venv` is Python 3.11 — it cannot install Django 6.
**Fix:** recreate local venv on 3.12+ before upgrading. Document in README.

### 3.4 MEDIUM: ADMINS tuple format deprecated in 6.0

`settings.py:33`: `ADMINS = [(str(env('ADMIN_NAME')), str(env('ADMIN_EMAIL')))]` — tuple form deprecated, removed later.
**Fix:** `ADMINS = [f'{env("ADMIN_NAME")} <{env("ADMIN_EMAIL")}>']`

### 3.5 Non-issues (verified, for the record)

`index_together`/`unique_together`, removed queryset internals, `ChoicesMeta`, `format_html()` no-args, `CheckConstraint(check=)`, positional `Model.save()`, `EmailMessage` API changes, `StringAgg ordering=`, `USE_L10N`, pytz — **zero hits**. Migrations already use explicit `BigAutoField`, matching the 6.0 default; no rewrites needed. `forms.URLField` now assumes `https` (affects Skill.url/Experience.url normalization only — desirable). `send_mail` usage is compliant.

### 3.6 Upgrade procedure

The audit recommends a two-step path; the deps branch already went direct 5.1.3 → 6.0.8 with `manage.py check` passing and a booted dev server. Either is defensible — **flagged for Morgan** (open question Q3).

1. Land `modernize/django6-deps` (requirements.txt fully re-pinned: Django 6.0.8, asgiref 3.12.1, django-phonenumber-field 8.5.0, phonenumbers 9.0.36, pillow 12.3.0, python-dotenv 1.2.2, sqlparse 0.5.5).
2. Fix ADMINS format in the settings pass (§2).
3. Validate: `python -Wd manage.py check` — must be warning-clean.
4. Smoke test: home, about, blog index + post detail, contact form submit, admin.
5. Deploy via existing Docker/Railway path (Python 3.13 image).

---

## 4. jQuery → Alpine.js Refactor (from t_ef37ad83)

Full inventory: `docs/audits/jquery-to-alpine-inventory.md`. Verdict: **trivial** — one 13-line file, two templates, one behavior, no AJAX.

### 4.1 Current footprint

- jQuery 3.7.1 CDN tags: `templates/index.html` (13–14), `templates/about.html` (5–6)
- `home/static/expand.js` (13 lines): hides all `.info`, then click handler on `.skill-button` that hides sibling `.info`s and toggles the clicked one (100ms linear) — an accordion over skill descriptions.
- All other templates (base, about_me, blog_index, contact, contact_success, logos, post_detail): **zero jQuery**.

### 4.2 Target design

**CDN swap (done):** base.html now has a proper `<head>` with Alpine v3.14.8 defer CDN (SRI-verified) and an `{% block extra_head %}`; index/about jQuery tags removed (commit 3753ea0).

**Behavior port (pending, t_830e9eb6):** two candidate patterns —

- **Pattern A — accordion (1:1 behavioral match):** one `x-data="{ open: null }"` on the skills container; each button sets `open = <index>`, `x-show="open === <index>"` on `.info`.
- **Pattern B — independent toggles (recommended):** each `.skill-button` gets `x-data="{ show: false }"`, `@click="show = !show"`, `x-show="show"` on `.info`. Cleaner; the close-others logic is barely noticeable across four skill categories on about.html.

**CSS cloak fix:** add `[x-cloak] { display: none !important; }` to `home/static/style.css` and `x-cloak` to each `.info` div (prevents flash of unhidden content before Alpine boots).

### 4.3 Files to change

| File | Change |
|------|--------|
| `templates/index.html` | add `x-data`/`@click`/`x-show`/`x-cloak` to skills loop; remove `expand.js` tag |
| `templates/about.html` | same, applied to all four skill loops |
| `home/static/expand.js` | **delete** |
| `home/static/style.css` | add `[x-cloak]` rule |

### 4.4 Risks

All low: FOUC (mitigated by `x-cloak`), animation jank (`x-transition` ≥ 100ms jQuery toggle), behavior drift (choose Pattern A or B deliberately), CDN availability (same risk profile as today's jQuery CDN).

---

## 5. Sequencing & Rollback

Execution order (each step independently revertable):

1. **Settings branch** (`modernize/settings`): commit working-tree settings changes (WhiteNoise/STORAGES/MEDIA/DATABASE_PATH) **plus** DEBUG parsing, ALLOWED_HOSTS split, ADMINS format, env fail-fast. Zero runtime behavior change with correct env values; verify with `manage.py check`.
2. **Deps branch** (`modernize/django6-deps`): rebase onto settings, re-run `python -Wd manage.py check`, smoke test. Rollback = revert requirements.txt.
3. **MyModel removal**: migration on top of 1+2. Rollback = `migrate home 0001` (table is empty either way).
4. **Alpine behavior port** (t_830e9eb6): templates + CSS + delete expand.js. Rollback = restore expand.js + script tags (git history).
5. **Prod DB reconciliation** (decisions ratified by Matt, 2026-08-10): contactme tables dropped and superuser hash stripped from sanitized seed (`prod-import/db.seed.sqlite3`); fresh superuser created via env vars at deploy time. Remaining: seed the Railway volume, then run migrations from steps 2–3 against the restored DB.

---

## 6. Test Plan

- `python -Wd manage.py check` — zero warnings on Django 6.0.8
- `python -Wa manage.py test` — suite is stubs, so real validation is smoke:
  - `/` (skills accordion works, no console errors)
  - `/about` (all four skill loops toggle)
  - `/blog` + a post detail page
  - contact form submit → email sends (or fails loudly in dev)
  - `/admin` login + list views
  - `python manage.py collectstatic` → WhiteNoise serves hashed assets
- Docker build on `python:3.13.0-alpine` + container boot via entrypoint.sh

## 7. Open Questions for Reviewers

1. **Alpine pattern A vs B** — exact accordion parity (A) or simpler independent toggles (B)? Wren recommends B.
2. **ADMINS format** — `"Name <email>"` string or bare email? Plan assumes `"Name <email>"`.
3. **Upgrade path** — audit recommended two-step 5.1.3 → 5.2 → 6.0; deps branch went direct to 6.0.8 and passed `manage.py check`. Accept direct, or redo as two-step for the paper trail?
4. **Settings scope** — salvage the fuller hardened settings.py from stash@{0} (fail-fast env validation, warnings cleanup), or keep the settings branch minimal (audit items only)?
5. **Media serving in prod** — MEDIA_* is future-proofing; no upload fields exist today. Confirm WhiteNoise-only static serving is enough and media stays out of scope for this cycle.

---

## Appendix: Source Audits

- `docs/audits/django-6-audit.md` — t_56d98bb7
- `docs/audits/jquery-to-alpine-inventory.md` — t_ef37ad83
- Settings/MyModel audit — kanban comment on t_47b9b79f (inline, no file artifact)
