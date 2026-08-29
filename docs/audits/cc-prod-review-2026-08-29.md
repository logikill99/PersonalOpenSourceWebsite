# VERDICT: SHIP

**The code is production ready. Merging PR #20 is unblocked and no code change is required
to go live. What is not ready is the deploy runbook — do not deploy by following it as
written.**

But if you deploy by following the PR body's step 3 / audit §6 env list *exactly*, you
ship a broken site: a homepage with a blank `<h1></h1>` and a contact form that
**silently discards every message while telling the visitor it was sent**. Both are
fixed by setting environment variables the runbook never mentions. That makes the
runbook — not the code — the thing blocking the deploy.

Four conditions before you press deploy. All are Railway-dashboard / ops changes:

| # | Condition | Consequence if skipped |
|---|-----------|------------------------|
| **C1** | Set `EMAIL_HOST_USER` + `EMAIL_HOST_PASSWORD` | Contact form silently eats every message (see F1) |
| **C2** | Set `LISTED_NAME`, `LISTED_TITLE`, `IN_TEXT_TITLE`, `LISTED_EMAIL`, `LISTED_GITHUB`, `LISTED_LINKEDIN`, `HOMEPAGE_IMAGE_CAPTION`, `ADMIN_EMAIL`, `ADMIN_NAME` | Homepage renders with an empty name/title (see F2) |
| **C3** | Fresh `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=mslevin.dev,www.mslevin.dev`, `DATABASE_PATH=/data/db.sqlite3` | Already in the runbook; C3 is just "don't drop these" |
| **C4** | **Confirm the volume is actually attached at `/data`** and survives a redeploy | Site boots green and works, then loses the whole database on the next deploy (see F4) |

Strongly recommended but not blocking: bump the base image off `python:3.13.0-alpine` (F3).

The through-line of C1, C2 and C4: this app's failure modes are quiet. Every one of them
returns HTTP 200 and looks healthy while doing the wrong thing. Nothing here crashes to
tell you it is misconfigured.

---

**Reviewer:** fresh-eyes pre-merge/pre-deploy pass, independent of the 2026-08-20 hardening
and the 2026-08-20 adversarial audit.
**Date:** 2026-08-29 · **Branch:** `salvage/railway-hardening` @ `9df2ced` · **PR:** #20
**Method:** read-only on git. Local venv + real `docker build`/`docker run` of the actual
Dockerfile, prod-like env, volume bind-mounted at `/data`, `X-Forwarded-Proto: https` to
simulate Railway's TLS edge. Scratch work in `/tmp`. Nothing was deployed.

---

## 1. The single most important fact

```
$ git diff --stat 91394f1..HEAD
 .env.example                                       |   3 +
 LOG.md                                             |  56 ++
 docs/audits/adversarial-smoke-review-2026-08-20.md | 707 +++++++++++++++++++++
```

**Only documentation has changed since the prior audit's last code fix.** The audit's
container-level evidence (privilege drop, XFF spoofing matrix, CSRF, 40-way parallel
POSTs, allowlist bypass re-tests) still describes the code as it exists now. I did not
need to re-derive it, and I independently re-confirmed the load-bearing parts below.

## 2. What I ran, and what came back

| Check | Result |
|---|---|
| `manage.py test` (local venv, Python 3.14) | **68 tests, OK** |
| `manage.py test` (**inside the built image, Python 3.13.0**) | **68 tests, OK** |
| `check --deploy --fail-level WARNING` (local, prod env) | **no issues, exit 0** |
| `check --deploy --fail-level WARNING` (inside running container) | **no issues, exit 0** |
| `makemigrations --check --dry-run` | **No changes detected** |
| `pip-audit -r requirements.txt` | **No known vulnerabilities found** |
| `docker build` from the real Dockerfile | **exit 0**, 247 MB |
| `collectstatic` build step (DEBUG=False, no ALLOWED_HOSTS) | **OK, 134 manifest entries** |
| Secret scan: tree + **every blob in git history** | **no real credentials** (see §4) |

### Container behaviour (prod env, simulated Railway edge)

```
/                     200      /health/         200      /admin/          302 + X-Robots-Tag: noindex
/about/               200      /robots.txt      200      /admin           301
/blog/                200      /favicon.ico     200      /static/style.css 200
/contactme/           200      /nonexistent/    404 (no traceback)
Host: evil.com     -> 400      plain HTTP /  -> 301 to HTTPS
PID 1 = appuser · touch /app/pwned -> Permission denied · Python 3.13.0
Headers: CSP (enforced), HSTS max-age=31536000; includeSubDomains; preload,
         nosniff, X-Frame-Options: DENY, Referrer-Policy, COOP
Static served from the hashed manifest: /static/style.3cb4f1afaed9.css
```

### The check that decides whether the deploy goes live at all

Railway probes the healthcheck path with `Host: healthcheck.railway.app` over plain
HTTP, while `SECURE_SSL_REDIRECT` is active. A 301 here fails the healthcheck and
Railway rolls the deploy back.

```
$ curl -si -H 'Host: healthcheck.railway.app' http://127.0.0.1:8099/health/ | head -1
HTTP/1.1 200 OK
```

**200, confirmed empirically.** `railway.toml`'s `healthcheckPath = "/health/"` matches
`urls.py:38`; `settings.py:84` adds `healthcheck.railway.app` to `ALLOWED_HOSTS`;
`settings.py:340` exempts it from the SSL redirect. `/healthcheck/` also returns 200.
This is correct and I verified it rather than reasoning about it.

Also a positive result I hit by accident: running the image without `SECRET_KEY` produced
`ImproperlyConfigured: SECRET_KEY environment variable is required. Refusing to start
without it.` The release gate fails closed.

---

## 3. Findings

### F1 — Contact form silently discards every message when `EMAIL_HOST_USER` is unset — **HIGH, must fix before deploy (env var)**

**Neither prior audit caught this.** It is reachable by following the project's own
documented runbook.

`contactme/views.py:36` sends to `[settings.EMAIL_HOST_USER]`. When that env var is unset
it defaults to `''` (`settings.py:136`), so the recipient list is `['']`. Django's
`EmailMessage.send()` short-circuits:

```python
def send(self, fail_silently=False):
    if not self.recipients():
        # Don't bother creating the network connection if there's nobody to send to.
        return 0
```

No exception is raised, so the view's `except` never fires. Verified end-to-end against
a container booted with **only** the PR-body step-3 env vars:

```
POST /contactme/  ->  302  ->  /contactme/success/
banner: []                       # no "Sending failed" warning
docker logs | grep -i smtp -> (nothing)
send_mail('s','b','from@x.com',[''], fail_silently=False)  ->  0
```

The visitor sees the success page. Nothing is logged. And because of the 2026-08-20
PII policy the message is **not persisted anywhere** — it is gone permanently.

Contrast, same container with `EMAIL_HOST_USER` set but bad SMTP creds — this path works
correctly:

```
SMTPSenderRefused: 530 5.7.0 Authentication Required
-> status 200, "Sending failed. Your message was not delivered" banner shown
```

So the failure mode is specifically *blank* config, not *wrong* config.

Why the test suite can't catch it: every contact test hardcodes the working case —
`contactme/tests.py:19`, `:107` and `PersonalHomePage/tests.py:242` all use
`@override_settings(EMAIL_HOST_USER="matt@example.com")`. There is no test for the unset
case, and `check --deploy` has no opinion about email config.

- **Blocking fix (do this):** set `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` in Railway.
- **Recommended follow-up (separate commit, not a merge blocker):** make this fail loudly.
  Either a custom Django system check that errors when `EMAIL_BACKEND` is SMTP and
  `EMAIL_HOST_USER` is blank — which the entrypoint's existing `check --deploy` gate would
  then enforce at boot — or an explicit guard in `contact_view` that renders the failure
  banner when there is no recipient. A silent discard is the worst available failure mode
  for the one form on the site.

### F2 — Following the documented runbook renders a homepage with no name — **MEDIUM, must fix before deploy (env vars)**

Container booted with exactly the PR-body step-3 list
(`SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG=False`, `DATABASE_PATH`, `DJANGO_SUPERUSER_*`):

```
$ curl -s .../ | grep -E '<title>|<h1'
<title>Developer Portfolio</title>
<h1></h1>                       # <- LISTED_NAME is ''

LISTED_NAME='' LISTED_TITLE='' LISTED_IN_TEXT_TITLE='' LISTED_EMAIL=''
LISTED_GITHUB='' LISTED_LINKEDIN='' HOMEPAGE_IMAGE_CAPTION=''
ADMINS=[]  SERVER_EMAIL='webmaster@localhost'
```

All of these default to `''` (`settings.py:152-170`) and are consumed unguarded by
`home/views.py`. Not a crash — a personal portfolio site with an empty name heading and
dead social links. `.env.example` documents them all correctly; the *deploy runbook* is
what omits them.

### F3 — Base image is pinned ~22 months behind — **MEDIUM, recommended before deploy**

`Dockerfile:1` pins `FROM python:3.13.0-alpine`. Measured, not inferred:

| | pinned `3.13.0-alpine` | floating `3.13-alpine` |
|---|---|---|
| CPython | **3.13.0** (Nov 2024) | **3.13.15** (Aug 2026) |
| Alpine | **3.20.3** | **3.24.1** |

That is 15 CPython patch releases of security and bug fixes not applied. The tag pins the
CPython patch level, so Docker Hub rebuilds do not help. Alpine 3.20 is also at/past the
end of its ~2-year support window, so its OS packages are no longer receiving fixes.

**This is the one gap neither prior audit could have closed:** `pip-audit` covers PyPI
packages only — it says nothing about the interpreter or the OS. No image scanner
(`trivy`/`grype`/`syft`) is installed on this machine, so **CPython and OS-package CVEs
were not scanned and I am not citing CVE IDs I cannot verify.** The staleness itself is
the finding.

**Fix:** change `Dockerfile:1` to `FROM python:3.13-alpine` (or pin `3.13.15-alpine`), then
rebuild and re-run the suite. Low risk — same minor version, and I confirmed the suite
passes inside the built image, so you have a direct before/after check.

### F4 — A missing volume is indistinguishable from a working one until the next deploy — **HIGH consequence, ops condition**

The entrypoint failure mode with the worst outcome on Railway, and the one no prior pass
tested. `entrypoint.sh:8-12` runs as root and does `mkdir -p "$DB_DIR"` + `chown -R`.
If `DATABASE_PATH=/data/db.sqlite3` is set but the volume is **not attached** (or is
mounted at a different path), all of that succeeds — against the container's ephemeral
writable layer. Verified:

```
$ docker run -d --env-file prod.env cc-prod-review:latest      # note: no -v
container state: running exit=0
migrations applied, gunicorn bound, GET / -> 200
$ docker exec ... ls -la /data/
-rw-r--r-- 1 appuser appuser 208896 db.sqlite3
$ docker exec ... grep -c " /data " /proc/mounts
0                                    # NOT a mount -> ephemeral container layer
```

Contrast, with the volume attached: `/proc/mounts` shows a real `/data` entry.

So a deploy with a forgotten or misconfigured volume comes up perfectly healthy, passes
the Railway healthcheck, serves the admin, accepts blog posts — and discards all of it on
the next redeploy. Nothing in `entrypoint.sh` or `check --deploy` distinguishes a mount
from an empty directory.

Not a code defect, and not worth adding a mount check to the entrypoint for a one-person
site. But it belongs in the runbook, which currently says only "mount Railway volume at
`/data`" with no verification step. **Verify it: create a blog post in the admin, trigger
a redeploy, confirm the post is still there.** That is the only check that actually proves
persistence.

### F5 — `railway.toml` lowers the healthcheck budget below Railway's default — **LOW**

`railway.toml:7` sets `healthcheckTimeout = 30`. Railway's own default is substantially
higher (documented as 300s at time of writing — **I could not verify this from here**, so
confirm against current Railway docs rather than trusting the number). Neither the PR nor
the audit explains the reduction.

The entrypoint does `check --deploy` → `migrate` → `createcachetable` → `createsuperuser`
before gunicorn binds. My cold-start boots completed in under 12s, so 30 probably holds —
but a first deploy against a seeded volume with more migrations to apply has less headroom
than the platform would have given it. **If the first deploy fails its healthcheck, raise
this value before debugging anything else.**

### F6 — Runbook accuracy (task item 5)

Verified against the code as it exists now.

| Runbook claim | Status |
|---|---|
| Volume at `/data`, `DATABASE_PATH=/data/db.sqlite3` | **Accurate.** Container booted, migrated, created the superuser, wrote the DB to the mount. |
| Seed DB at `/home/slab/sandboxes/hermes-wren/work/prod-import/db.seed.sqlite3` | **Accurate — file exists**, 253,952 bytes, mtime 2026-08-17 22:49. `scripts/railway-volume-setup.sh:77` and PR step 2 are still valid. (Without it the site ships empty but functional — migrate + createsuperuser succeed.) |
| PR body: "13 tests, all passing" | **Stale.** Actual: **68**. |
| PR step 3 env list | **Incomplete** — omits everything in F1 and F2. |
| Audit §6 condition 1 (fresh `SECRET_KEY`) | Accurate. |
| Audit §6 condition 2 (`DATABASE_PATH` required) | Accurate — confirmed `/app` is unwritable to `appuser`. |
| Audit §6 condition 3 (watch logs for `not in TRUSTED_PROXY_IPS`) | Accurate; the log line exists and fires (`ratelimit.py:114`). Advice not to set `TRUSTED_PROXY_IPS` pre-emptively is correct. |
| Audit §6 condition 4 (`ADMIN_IP_ALLOWLIST` now holds) | Accurate. |
| `README.md` | **Stale**, unrelated to this PR. Says Django 5.1 / pillow / PythonAnywhere, documents the old quoted `.env` format, and never mentions Railway or `DATABASE_PATH`. Cosmetic; flagging for completeness. |

### F7 — `.gitignore` / `.dockerignore` do exclude what they claim, with one wrinkle — **LOW**

Verified by `git ls-files`, not by reading the ignore file:

- `db.sqlite3` — **0 tracked** ✓ · `staticfiles/` — **0 tracked** ✓ · `.env` — **not in HEAD** ✓
- `.dockerignore` correctly excludes `.env`, `*.sqlite3`, `staticfiles/`, `.venv`, `docs/`, `prod-import/`. Build context is clean; the image builds static at `Dockerfile:15` rather than copying them in. ✓
- **Wrinkle:** `.gitignore` lists `.idea/` but **7 `.idea/` files are already tracked**. `.gitignore` does not untrack files that were committed before the rule existed. I read them — no secrets, just IDE scaffolding (a stale "Python 3.12" SDK name). Harmless, but the ignore rule is not doing what it looks like it does. `git rm -r --cached .idea` if you care.

### F8 — SQLite is running on default journal settings — **LOW, robustness recommendation**

`DATABASES['default']` (`settings.py:228`) sets no `OPTIONS`: no WAL, no
`transaction_mode`, no explicit `timeout`. With 2–3 gunicorn workers plus a
`DatabaseCache` write on every rate-limited POST, rollback-journal mode makes readers
block writers. The prior audit's 40-way parallel POST test found zero
`database is locked`, so this is not a defect — just the cheap hardening available if
write contention ever appears:

```python
'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE',
            'init_command': 'PRAGMA journal_mode=WAL;'}
```

Note WAL needs the `-wal`/`-shm` sidecar files on the same volume — fine at `/data`.

### F9 — Already-known, re-confirmed, not re-litigated

`home.MyModel` dead model (audit L7) and the duplicate `/contactme/` + `/blog/` routing
between `home/urls.py` and `PersonalHomePage/urls.py` (audit L10) are both still present
and both still cosmetic. `home/admin.py` defines the class name `ExperienceAdmin` twice
(the first registers `Skill`) — harmless, both models register correctly.

**Explicitly checked and NOT a problem:** gunicorn does not pass `--forwarded-allow-ips`,
but Django reads `HTTP_X_FORWARDED_PROTO` from `META` via `SECURE_PROXY_SSL_HEADER`
directly, so gunicorn's default only affects `wsgi.url_scheme`, which nothing consumes.
HSTS, secure cookies and CSRF all behaved correctly behind the simulated edge.

---

## 4. Secrets: the `.env` blob in history is a false alarm

The PR body and audit R6 both flag "the public `.env` blob on `main` (`7b0fd2b`)" as the
project's largest open risk and call for credential rotation. **I dumped it. It contains
only placeholders:**

```
SECRET_KEY = "1234"
EMAIL_HOST_PASSWORD = "thes isas ampl pswd"
EMAIL_HOST_USER = "makesuretochangethis@sample.com"
```

I then scanned **every blob in the entire repository history** for high-entropy
`SECRET_KEY`, 16-char Gmail app passwords, `ghp_*`, `AKIA*`, and PEM headers. The only
hits are `change-me-to-a-random-secret-key` in `.env.example` and the deliberately fake
`x7Qvkd9wPzR3...` fixture in `PersonalHomePage/tests.py:155`.

**No real credential has ever been committed to this repository.** The history purge is
housekeeping, not an incident, and R6 can be downgraded. You should still generate a fresh
`SECRET_KEY` for production (audit condition 1) — that is normal hygiene, not remediation.

---

## 5. Bottom line

The engineering on this branch is genuinely good and the prior adversarial audit was
honest about its own gaps — which is why the remaining issues are all in the *deploy
instructions* rather than the code. I re-verified the load-bearing security claims against
a freshly built image instead of taking them on trust, and they hold: privilege drop,
read-only `/app`, enforced CSP, HSTS, host-header rejection, CSRF, admin allowlist, and
the boot-time release gate all behave as documented.

**Merge PR #20.** Before deploying, set the env vars in C1/C2, and bump the base image
(F3) if you want the deploy to start on a supported interpreter. Then on first boot,
confirm the three things the audit's R7 correctly flags as unverifiable from here: a real
contact email actually arrives, `/admin/` is reachable, and the logs are free of
`not in TRUSTED_PROXY_IPS`.

Given F1 and F4, that first-boot contact-email test is not optional — it is the only thing that
distinguishes "working" from "silently discarding mail."
