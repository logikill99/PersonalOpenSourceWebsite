# Django 5.1.3 -> 6.x Deprecation & Breaking-Change Audit

Repo: /home/wren/work/PersonalOpenSourceWebsite
Audited: 2026-08-06 against official release notes for Django 5.1, 5.2, 6.0, 6.1.
Scope: all project Python code, settings, requirements.txt, templates, Dockerfile.

## Verdict

The codebase is small and uses a modern, vanilla subset of Django (function
views, ModelForm, standard ORM, `{% load static %}`, BigAutoField everywhere).
There is exactly ONE blocker-class issue and a handful of cleanups. Nothing in
the project code itself will crash on Django 6.0/6.1.

---

## 1. BLOCKER: `django-phonenumber-field==8.0.0` does not support Django 6

- requirements.txt pins `django-phonenumber-field==8.0.0`.
- PyPI metadata for 8.0.0 declares Django classifiers only up to 5.0
  (requires_dist is just `Django>=3.2`, but the release predates Django 6 and
  its `EmailMessage`/form-renderer removals — the project actively added
  Django 6 support in 8.4/8.5).
- Latest release is **8.5.0**, which explicitly classifies
  `Framework :: Django :: 5.2` and `Framework :: Django :: 6.0` and requires
  `Django>=4.2`.

Remediation:
  requirements.txt -> `django-phonenumber-field==8.5.0`
  (also bump `phonenumbers` from 8.13.49 to a current 9.x release while
  there; it is a data-only library and safe to float.)

Used in: contactme/models.py (PhoneNumberField model field),
contactme/forms.py (PhoneNumberField form field), settings.py INSTALLED_APPS.

---

## 2. HIGH: `asgiref==3.8.1` below Django 6.0 minimum

Django 6.0 raises the minimum supported asgiref from 3.8.1 to **3.9.1**.
requirements.txt pins `asgiref==3.8.1` — pip will refuse the combination or
silently upgrade it.

Remediation:
  requirements.txt -> `asgiref>=3.9.1` (or drop the pin entirely; Django
  declares its own floor).

---

## 3. HIGH: `pillow==11.0.0` minimum is fine, but Python floor matters

Django 6.0 requires **Python >= 3.12**.
- Dockerfile already uses `python:3.13.0-alpine` — OK.
- The checked-out local `.venv/` in the repo is Python **3.11** — any local
  run with that venv will fail to install Django 6. Recreate the venv with
  3.12+ before upgrading. (The venv also shouldn't be in the repo at all —
  it's gitignored already per task t_8f0ab63b's hygiene commit; just noting
  the runtime floor.)

Pillow 11.0.0 satisfies Django 6.0's minimum (10.1.0+), but bumping to a
current 11.x/12.x is recommended for security fixes.

---

## 4. MEDIUM: Deprecation warning — `ADMINS` as list of tuples

settings.py line 33:
    ADMINS = [(str(env('ADMIN_NAME')), str(env('ADMIN_EMAIL')))]

Django 6.0 deprecates setting ADMINS/MANAGERS as a list of (name, address)
tuples; it will be removed in a future release. Django never used the name
portion.

Remediation (new format):
    ADMINS = [f'{env("ADMIN_NAME")} <{env("ADMIN_EMAIL")}>']
or simply:
    ADMINS = [str(env('ADMIN_EMAIL'))]

This is warning-only in 6.x but will hard-fail in a later release. Fix now
while the file is open.

---

## 5. LOW / informational: `send_mail` positional args in contactme/views.py

contactme/views.py calls:
    send_mail('New Message', f'...', settings.EMAIL_HOST_USER,
              [settings.EMAIL_HOST_USER], fail_silently=False)

Django 6.0 deprecates positional arguments for `fail_silently` and later
parameters of send_mail()/mail_admins()/etc. — they must become keyword
arguments. The call above passes only the first four positionally (subject,
body, from_email, to), which is still allowed, and `fail_silently` is already
keyword. **No change required**, but keep it that way when editing.

---

## 6. LOW: `STATIC_URL = '/static/'` (no leading-slash requirement change)

Django 6.0 did not remove STATIC_URL, but note the long-term direction is the
STORAGE-based static config. The current value `/static/` is valid in 5.2,
6.0, and 6.1. **No change required** for this upgrade. If touching it later,
migrate to:
    STORAGES = {"staticfiles": {"BACKEND":
        "django.contrib.staticfiles.storage.StaticFilesStorage"}}
…or just leave it; `{% load static %}` + `{% static %}` usage in the four
templates (base.html, index.html, about.html, gitgraph.html) is fully
compatible as-is.

---

## 7. Confirmed NON-ISSUES (checked explicitly)

Searched the whole tree for the following 6.0/6.1 removals — zero hits:

- `index_together` / `unique_together` (removed in 6.0 migrations) — not used.
- `get_prefetch_queryset`, `get_joining_columns`,
  `get_reverse_joining_columns`, `Prefetch.get_current_queryset` — not used.
- `format_html()` without args — not used.
- `ChoicesMeta` alias (removed 6.0) — not used.
- `register_converter` overrides — not used; home/urls.py imports `re_path`
  but never calls it (dead import, harmless).
- `FORMS_URLFIELD_ASSUME_HTTPS` transitional setting — not set. Note the
  behavior change: forms.URLField now defaults to scheme `https` instead of
  `http`. home/models.py uses `models.URLField()` for Skill.url and
  Experience.url — validation-only effect: previously `example.com` input
  normalized to `http://example.com`, now `https://example.com`. Existing
  stored data is untouched. Almost certainly desirable for this site.
- `request` required in `ModelAdmin.lookup_allowed()` — no custom ModelAdmin
  methods; all three admin.py files are bare `@admin.register` stubs.
- `ModelAdmin.log_deletion` / `LogEntryManager.log_action` — not used.
- `CheckConstraint(check=...)` — not used.
- `OS_OPEN_FLAGS` FileSystemStorage attr — not used.
- `django.utils.itercompat` — not used.
- Positional args to `Model.save()` / `BaseConstraint` — not used.
- `urlize`/`urlizetrunc` filters — not used in templates.
- `StringAgg`/`ArrayAgg`/`JSONBAgg` `ordering=` kwarg (removed 6.1) — SQLite
  project, not used.
- `RemoteUserMiddleware` subclasses — not used.
- `staticfiles.finders.find(all=...)` (removed 6.1) — not used.
- `USE_L10N` (removed long ago) — not set.
- `pytz` / naive datetimes — not used; only `auto_now`/`auto_now_add` fields,
  which are timezone-aware under `USE_TZ = True` (correctly set).
- Migrations: all use `models.BigAutoField` explicitly; matches the new 6.0
  default for DEFAULT_AUTO_FIELD (settings.py already sets it, apps.py files
  already set `default_auto_field`). No migration rewrites needed.
- Email: `send_mail` is the only mail API used — no EmailMessage subclasses,
  no MIMEBase attachments, no SafeMIMEText. The 6.0 "modern email API"
  adoption is a non-event for this project.
- Database: SQLite in use. Django 5.1 raised minimum SQLite to 3.31.0 —
  Python 3.13's bundled sqlite3 is 3.45+, fine. MariaDB/PostgreSQL version
  drops are irrelevant.

---

## Remediation checklist (in order)

1. requirements.txt:
   - `Django==5.1.3` -> `Django==5.2.x` first (LTS waypoint), then `6.0.x`.
     Recommend upgrading in two steps: 5.1.3 -> 5.2 (run site, check for
     warnings with `python -Wd manage.py check`), then 5.2 -> 6.0.
   - `asgiref==3.8.1` -> `asgiref>=3.9.1`
   - `django-phonenumber-field==8.0.0` -> `django-phonenumber-field==8.5.0`
   - `phonenumbers==8.13.49` -> current 9.x
   - `pillow==11.0.0` -> current (11.3+/12.x)
   - `sqlparse==0.5.1` -> fine as-is (Django 6 wants >=0.5.0)
   - `python-dotenv==1.0.1` -> unaffected by Django upgrade

2. settings.py:
   - Change ADMINS tuple to the new string format (item 4).

3. Runtime:
   - Ensure deployment targets Python >= 3.12. Dockerfile already on 3.13.
   - Recreate the local dev venv on 3.12+ (current .venv is 3.11).

4. Validation:
   - `python -Wd manage.py check` on 5.2 first; fix any
     RemovedInDjango60Warning before bumping to 6.0.
   - `python -Wa manage.py test` (tests.py files are stubs, so real
     validation = smoke-test the site: home, about, blog, contact form
     submit, admin).

## Bottom line

One true dependency blocker (django-phonenumber-field), one version floor
(asgiref), one Python floor (3.12+ for local dev), one trivial settings
cleanup (ADMINS). Estimated effort: < 1 hour including the two-step upgrade
and smoke test. The project code itself needs zero changes.
