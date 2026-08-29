# Adversarial Smoke Test, Attack Run & Code Review — `salvage/railway-hardening`

**Date:** 2026-08-20
**Reviewer:** independent review pass (Claude Code / opus) under `AGENTS.md`
**Branch reviewed:** `salvage/railway-hardening`, base tip `b922e76`
**Pre-hardening comparison point:** `8dfb907`
**Scope:** the 11 hardening commits `b5e4419..b922e76` plus everything they touch
**Posture:** the branch was treated as untrusted code that *claims* to be production-hardened.

> Verdict, fixes landed, and residual risks are at the bottom. Everything above is
> raw evidence: exact commands and their actual output.

---

## 0. Test rig

Three environments were used. All findings below name which one produced them.

| Rig | What it is | Why |
|-----|-----------|-----|
| **local** | `.venv` + `manage.py`, prod-ish env vars | test suite, `check --deploy` matrix |
| **container** | the real `Dockerfile` image, `docker run` + volume | privilege drop, entrypoint, gunicorn |
| **container + TLS edge** | a Python TLS-terminating reverse proxy on `:8443` in front of the container, which **appends** the peer IP to `X-Forwarded-For` and sets `X-Forwarded-Proto: https` | faithfully simulates Railway's edge, so Secure cookies, HSTS, CSRF-over-HTTPS and the XFF logic all behave as they will in production |

```bash
# image
docker build -t pow-audit:base .

# container (throwaway volume, throwaway superuser — never Matt's local db.sqlite3)
docker run -d --name pow --env-file /tmp/audit/prod.env -v /tmp/audit/data:/data -p 8099:8000 pow-audit:base

# simulated Railway edge (script: /tmp/audit/tlsproxy.py)
python3 /tmp/audit/tlsproxy.py     # https://mslevin.dev:8443 -> http://127.0.0.1:8099
```

The lab-only wrinkle worth stating so the evidence reads correctly: because the edge
listens on `:8443`, `Host`/`Origin`/`Referer` carry an explicit port. Django's CSRF
origin check compares host-with-port, so the proxy forwards `Host: mslevin.dev:8443`.
Two early "403" results in this audit were that mismatch, not a defect — both are
called out where they appear. In real production (`:443` implicit) the mismatch
cannot occur.

---

## 1. Track A — Smoke test

### 1.1 Test suite (local)

```
$ python manage.py test
Ran 40 tests in 0.941s
OK
```

### 1.2 `check --deploy` matrix (local, prod-like)

| Env | Result |
|-----|--------|
| Clean prod env, security vars **unset** | `System check identified no issues` — exit 0 |
| `DJANGO_TEST=1` injected into a prod env | W008 + W012 + W016 raised — **gate correctly refuses the boot** |
| `TRUST_PROXY=` `SECURE_SSL_REDIRECT=` `SECURE_HSTS_PRELOAD=` set to **empty strings** | W008 + W021 — **boot refused** (see finding **H2**, this is the exact shape `.env.example` tells you to write) |

### 1.3 Every public path (container, plain HTTP — `SECURE_SSL_REDIRECT` active)

```
/                    301 -> https://mslevin.dev/          /health/        200
/about/              301                                  /healthcheck/   200
/blog/               301                                  /robots.txt     301
/contactme/          301                                  /favicon.ico    301
/contactme/success/  301                                  /admin/login/   301
```

Health endpoints are correctly exempt (`SECURE_REDIRECT_EXEMPT`); everything else
redirects to HTTPS. Railway's healthcheck will not be redirect-looped.

### 1.4 Every public path (container, `X-Forwarded-Proto: https`)

```
/                    200 text/html      3892b     /robots.txt        200 text/plain   71b
/about/              200 text/html      3071b     /favicon.ico       200 image/svg+xml 190b
/blog/               200 text/html       806b     /static/style.css  200 text/css   11965b
/blog/post/1/        200 text/html                /static/resume.pdf 200 application/pdf 9409b
/contactme/          200 text/html      2116b     /static/1.jpg      200 image/jpeg 70599b
/contactme/success/  200 text/html       897b     /admin/login/      200 text/html  4158b
/health/             200 application/json  16b    /admin/            302 -> /admin/login/?next=/admin/
/healthcheck/        200 application/json  16b    /nope404/          404
```

All green. `/blog/post/<pk>/` is the real route — note `blog/urls.py` uses
`post/<int:pk>/`, not `/blog/<pk>/`.

### 1.5 Security headers (container + TLS edge, real HTTPS)

```
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net
  'unsafe-eval'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self';
  object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Cross-Origin-Opener-Policy: same-origin
```

- Present on HTML, on `/health/` JSON, **and** on WhiteNoise static responses.
- HSTS is correctly **absent** on plain HTTP and present only on forwarded-HTTPS.
- Enforced, not report-only. No `unsafe-inline` anywhere.

Cookie flags, captured from a real login:

```
csrftoken=...;  Path=/; SameSite=Lax; Secure                    (no HttpOnly — correct, Django needs JS read access)
sessionid=...;  Path=/; SameSite=Lax; Secure; HttpOnly          (correct)
```

### 1.6 Browser verification (headless Chrome 
via puppeteer-core, enforced CSP, real TLS)

Public pages — `/`, `/about/`, `/blog/`, `/blog/post/1/`, `/contactme/`, `/contactme/success/`:

```
alpine=true  x-data=N  initialized=N  x-cloak-left=0
CSP violations: 1 on EVERY page  ->  Refused to load stylesheet
  'https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap'
  violates directive "style-src 'self'"
```

Alpine boots, every `x-data` component initializes, no `x-cloak` is left stranded,
and the skill accordion genuinely toggles under the enforced policy:

```
Alpine accordion: display before click = none | after click = block | toggles = true
```

But the Google Fonts `@import` is blocked on every single page — see finding **M1**.

Authenticated admin (the pages that actually matter for moderation, not just the login form):

```
/admin/                        200  CSP violations: none
/admin/blog/comment/           200  CSP violations: none   (changelist + list_filter + actions dropdown present)
/admin/blog/post/add/          200  CSP violations: none   (M2M widget)
/admin/blog/post/              200  CSP violations: none
/admin/auth/user/              200  CSP violations: none
/admin/home/experience/add/    200  CSP violations: none
/admin/blog/comment/1/change/  200  CSP violations: none
```

**The Django 6 admin is fully CSP-clean under this policy** — zero inline `<style>`
tags, zero inline `<script>`, and the two `[style]` attributes on the add form are
set by admin JS through the CSSOM (which CSP does not police). This was the most
likely place for the hardening to have quietly broken something; it did not.

Bulk moderation exercised end to end in the browser:

```
comments listed: 3  ->  select all  ->  action "approve_comments"  ->  submit
APPROVED: [('P0', True), ('P1', True), ('P2', True)]
```

### 1.7 Docker privilege drop (container)

Every claim in LOG.md §Docker was re-tested **as `appuser`** (`docker exec -u appuser`;
note plain `docker exec` lands you as root because the image has no `USER` directive,
which is expected given the entrypoint does the drop):

```
PID   USER      COMMAND
  1   appuser   gunicorn          <- PID 1 is unprivileged
 18   appuser   gunicorn
 19   appuser   gunicorn

$ id                              uid=10001(appuser) gid=10001(appuser)
$ touch /app/evil2                Permission denied
$ echo x >> /app/PersonalHomePage/settings.py   Permission denied
$ touch /app/templates/base.html  Permission denied
$ su-exec root id                 su-exec: setgroups: Operation not permitted   (exit 1)
$ touch /data/probe               ok                 <- volume writable, as intended
$ ls -ln /data                    -rw-r--r-- 1 10001 10001 db.sqlite3
```

All LOG.md Docker claims hold. Running code cannot modify itself, cannot re-escalate,
and the volume is correctly chowned by the root-phase of the entrypoint.

*(`appuser` can read `/proc/1/environ` — but PID 1 **is** `appuser`, and the secret is
already in that process's own environment. Not a finding.)*

### 1.8 Entrypoint / release gate (container)

- `SECRET_KEY` unset → image refuses to start with `ImproperlyConfigured`. Verified.
- Migrations, `createcachetable`, and `createsuperuser --noinput` all ran on first boot
  against the mounted volume; second boot reported the superuser already existed.
- `WEB_CONCURRENCY` cap and gunicorn stdout logging confirmed in `docker logs`.
- **`DATABASE_PATH` is effectively mandatory.** With it unset the entrypoint skips the
  chown block, `NAME` falls back to `/app/db.sqlite3`, and `/app` is root-owned by
  design, so `migrate` dies:
  ```
  django.db.utils.OperationalError: unable to open database file
  ```
  Correct fail-closed behaviour, but it is an undocumented hard requirement (**I1**).

---

## 2. Track B — Adversarial testing

Format: **what was tried → what a hardened app should do → what actually happened.**

### 2.1 CSRF (container + TLS edge, real browser-equivalent flow)

| # | Attempt | Expected | Actual |
|---|---------|----------|--------|
| 1 | valid token + cookie + same-origin `Referer` | 302 success | **302 → `/contactme/success/`** |
| 2 | no `csrfmiddlewaretoken` in body | 403 | **403** |
| 3 | forged token (`"A"*64`) | 403 | **403** |
| 4 | valid token, cookie stripped | 403 | **403** |
| 5 | cross-origin `Referer: https://evil.example/x` | 403 | **403** |
| 6 | no `Referer` at all over HTTPS | 403 | **403** |
| 7 | `Origin: https://evil.example` | 403 | **403** |
| 8 | cookie from session A + token from session B | 403 | **403** |

**CSRF: no bypass found.** Note this was entirely unverified by the existing test
suite — see finding **M4**.

### 2.2 Rate limiting / `X-Forwarded-For` spoofing

**Through the simulated Railway edge (proxy appends the real peer):**

```
6 contact POSTs, each with a different forged X-Forwarded-For (10.0.0.0-5):
   0:302/sent 1:302/sent 2:302/sent 3:200/LIMITED 4:200/LIMITED 5:200/LIMITED
```
Rotation defeated. Rightmost-entry parsing works as designed. ✅

Admin login brute force through the edge, rotating XFF each attempt:
```
   0:200 1:200 2:200 3:429 4:429 5:429
```
Throttled. ✅

**Direct to gunicorn (nothing appends XFF) — the bypass:**

```
6 contact POSTs, rotating spoofed X-Forwarded-For, no proxy in path:
   0:302/SENT 1:302/SENT 2:302/SENT 3:302/SENT 4:302/SENT 5:302/SENT     <- limiter fully bypassed
control, same run, NO X-Forwarded-For header:
   0:302/SENT 1:302/SENT 2:302/SENT 3:200/LIMITED 4:200/LIMITED 5:200/LIMITED
```

See finding **H1** — same root cause as the admin bypass below.

Other limiter probes:
- Invalid-form floods do **not** consume budget (10 invalid posts, then a valid post still 302s). Deliberate and correct for spam, but it means the endpoint itself is unmetered (**L4**).
- Honeypot posts return 302→success, indistinguishable from a real send, and are also unmetered.
- 20-way parallel POST storm: see 2.7.

### 2.3 Admin IP allowlist bypass — **HIGH**

Container booted with `ADMIN_IP_ALLOWLIST=203.0.113.7` (an address the client is not):

```
GET /admin/login/  no XFF                              404   <- correct
GET /             (public sanity)                      200   <- correct
GET /admin/login/  X-Forwarded-For: 203.0.113.7        200   <- *** BYPASS ***
GET /admin/login/  X-Forwarded-For: 1.1.1.1, 203.0.113.7  200   <- *** BYPASS ***
GET /admin/login/  X-Forwarded-For: 203.0.113.7, 8.8.8.8   404   <- correct (proxy appended)
```

One client-supplied header turns the allowlist off. Full write-up in **H1**.

Existence leaks around the same control:
```
GET /admin  (no trailing slash)          301 -> /admin/          (leaks, even when allowlisted out)
GET /static/admin/css/base.css           200                      (leaks)
GET /robots.txt                          Disallow: /admin/        (advertises it outright)
```

### 2.4 XSS

Comment payload `<img src=x onerror=alert(1)>` (author) + `<script>alert(document.domain)</script><svg/onload=alert(2)>` (body):

```
POST -> 302
stored: '<img src=x onerror=alert(1)>'  approved=False
pre-approval : payload rendered? False | "awaiting moderation" shown: True
post-approval: raw payload rendered? False | HTML-escaped? True
  | On Aug. 20, 2026 <b>&lt;img src=x onerror=alert(1)&gt;</b> wrote:
  | <p>&lt;script&gt;alert(document.domain)&lt;/script&gt;&lt;svg/onload=alert(2)&gt;</p>
```

Contact fields reflected into the re-rendered form: raw payload absent, `&lt;script&gt;` present.

**No XSS found in any visitor-controllable field.** The moderation gate holds and the
autoescape holds independently of it. The only `|safe` sink (`post.body`, `post_detail.html:10`)
is admin-authored — discussed in **L5**.

### 2.5 Email header injection

`first_name = "Ada\nBcc: e@zz.io"` (within the 30-char field limit so the form validates):

```
--- HEADER BLOCK ---            --- BODY ---
Content-Type: text/plain        You have a new message from Ada
Subject: New Message            Bcc: e@zz.io L.
From: matt@example.com
To: matt@example.com
=> 'Bcc: e@zz.io' in header block? False   in body? True
```

**Blocked.** Subject/From/To are all static settings in `contactme/views.py:29-38`;
user data reaches the body only, and Django's `forbid_multi_line_headers` backstops
the headers regardless. Nothing to fix.

### 2.6 Host header / ALLOWED_HOSTS / traversal / redirects / info leak

```
Host: evil.example                          400        Host: mslevin.dev              200
Host: mslevin.dev.evil.example              400        Host: healthcheck.railway.app  200
X-Forwarded-Host: evil.example              400        X-Forwarded-Host: healthcheck.railway.app 200

/static/../PersonalHomePage/settings.py     404        /db.sqlite3     404      /media/      404
/static/..%2f..%2fPersonalHomePage/...      404        /.env           404      /media/x.jpg 404
/static/%2e%2e/%2e%2e/manage.py             404        /.git/config    404      /static/     404

/admin/login/?next=https://evil.example     200 (no redirect)   -- Django validates `next`
/admin/login/?next=//evil.example           200 (no redirect)
/blog/post/99999/  404   /blog/post/0/  404   /blog/post/-1/  404   /blog/post/1%20or%201=1/  404

404 body: plain "Not Found" — 0 occurrences of traceback/DEBUG/urlpatterns
```

No host-header bypass, no traversal, no open redirect, no DEBUG leakage, no
DEBUG-served media (the `static()` hook really is gone). `X-Forwarded-Host:
healthcheck.railway.app` is accepted but there is no link-generation or
password-reset flow to poison with it (**I2**).

### 2.7 Mass assignment & SQLite concurrency

Extra fields `approved=true&id=999&post=1` posted with a comment:
```
approved= False  pk= 1        <- ignored; the view constructs Comment from cleaned_data only
```

20-way parallel / 40 total comment POSTs against the container:
```
status distribution: {302: 3, 200: 37}
COMMENTS_CREATED 3
log contains 'database is locked': 0
log contains 'OperationalError': 0
log contains '500 ': 0
```

The read-modify-write race LOG.md accepts as "~1 extra post" did not even manifest —
exactly 3 comments from 40 concurrent attempts, and **no SQLite lock contention** at
this concurrency. The DatabaseCache limiter genuinely is shared across workers.

### 2.8 Dependencies

```
$ pip-audit -r requirements.txt
Found 4 known vulnerabilities in 1 package
sqlparse 0.5.5  PYSEC-2026-3696/3697/3698/3699   Fix: 0.6.0
```

Three ReDoS/DoS parser issues and one code-generation escaping issue. `sqlparse` is a
transitive Django dependency used only for `sqlformat` (debug SQL display,
`sqlmigrate`); no attacker-controlled SQL text reaches it in this app, so real-world
reachability is ~nil. Still a free pin bump — **M2**.

---

## 3. Track C — Code review, ranked findings

Severity is *for this site*: a personal portfolio, single admin, no user accounts,
no payment, no PII at rest. "HIGH" here means "would block the deploy", not
"internet-wide emergency".

### HIGH

---

#### H1 — Admin IP allowlist is turned off by one client-supplied header — **FIXED**

**Location:** `PersonalHomePage/ratelimit.py:40-44` (`client_ip`), consumed by
`PersonalHomePage/middleware.py:53-58` (`AdminAccessMiddleware._allowed`).

`client_ip()` reads the **rightmost** `X-Forwarded-For` entry whenever `TRUST_PROXY`
is on — and `TRUST_PROXY` defaults to `not DEBUG`, i.e. **on in production**
(`settings.py:84`). Rightmost-is-trustworthy holds only if a proxy actually appended
an entry. A request that reaches gunicorn without traversing Railway's edge carries
whatever `X-Forwarded-For` the attacker typed, so its rightmost entry is
attacker-chosen. `ratelimit.py` reasons carefully about *ordering* within the header
and never asks whether the header should be believed at all.

**Repro** (§2.3): container with `ADMIN_IP_ALLOWLIST=203.0.113.7`,
`curl -H 'X-Forwarded-For: 203.0.113.7' .../admin/login/` → **200** instead of 404.

**Impact:** the allowlist — the control LOG.md recommends Matt turn on — is a no-op
against anyone who can reach the container's port directly. The password is still the
real gate, so this is a defence-in-depth failure, not direct compromise.

**Exploitability, stated honestly:** *not* reachable through Railway's public edge
**if** Railway appends to `X-Forwarded-For`, which is the documented behaviour and
which I could not verify from here. It becomes live the moment anything else can
reach the port — Railway private networking, a second proxy (Cloudflare in front of
Railway would also break the rightmost assumption in the other direction), a port
exposed during debugging, or this image run anywhere else.

**The test that hid it:** `PersonalHomePage/tests.py:253`,
`test_spoofed_xff_does_not_grant_admin_access`, pinned `TRUST_PROXY=False` — asserting
safety in the one configuration production never runs. It passed, and it was
meaningless.

**Fix landed** (`3da631b`): new `TRUSTED_PROXY_IPS` setting names the socket peers
whose forwarded headers are believed — the rule nginx spells `set_real_ip_from` and
gunicorn spells `forwarded-allow-ips`. `client_ip(require_trusted_peer=True)` fails
closed and is used by the admin allowlist only. Default (loopback + RFC1918 + CGNAT +
IPv6 ULA/link-local) is exactly what a container behind a platform edge sees, so the
Railway deployment is unchanged. Rejections log the peer so a self-lockout is
diagnosable from Railway logs.

Deliberately **not** applied to the rate limiter: there, over-trusting costs a few
extra posts, while over-restricting collapses every visitor into one bucket — a
self-DoS. Asymmetric strictness is the point, and it is documented in the module
docstring.

**Re-verified after fix** (§4).

---

#### H2 — A blank security env var refuses the boot — **FIXED**

**Location:** `PersonalHomePage/settings.py:28-40` (`env_bool`), triggered by
`entrypoint.sh:26`.

`env_bool` returned `False` for an empty string. `.env.example` documents the exact
opposite for three security settings — `TRUST_PROXY=`, `SECURE_SSL_REDIRECT=`,
`SECURE_HSTS_PRELOAD=` are each annotated "defaults to true when `DEBUG=False`" — and
Railway's dashboard stores empty strings for declared-but-blank variables.

**Repro:**
```
$ TRUST_PROXY= SECURE_SSL_REDIRECT= SECURE_HSTS_PRELOAD= manage.py check --deploy --fail-level WARNING
?: (security.W008) Your SECURE_SSL_REDIRECT setting is not set to True.
?: (security.W021) You have not set the SECURE_HSTS_PRELOAD setting to True.
System check identified 2 issues  ->  exit 1
```
`entrypoint.sh` runs precisely that command as a release gate, so the container
crashloops on Railway. Following our own documented configuration bricks the deploy.

**Impact:** deploy-blocking. Note the gate *fails closed*, which is correct — the bug
is that blank ever meant "off". Without the gate this would instead have been a live
site with no HTTPS redirect.

**Fix landed** (`dfaca49`): blank and whitespace-only fall through to the caller's
default; explicit `0`/`false`/`no`/`off` still mean False. New `DeployGateTests` run
the real `check --deploy` in a subprocess across four env shapes and pin the gate in
**both** directions, so it cannot be softened into uselessness: clean prod passes,
blank-var prod passes, `SECURE_SSL_REDIRECT=False` must still raise W008, and
`DJANGO_TEST=1` leaking into prod must still raise W008+W012+W016.

---

### MEDIUM

#### M1 — Enforced CSP breaks the site's typography on every page — **FIXED**

`home/static/style.css:3` `@import`s Roboto from `fonts.googleapis.com`; `style-src
'self'` blocked it site-wide and the site silently fell back to generic sans-serif
(§1.6). Invisible to header inspection and to the test suite — only a browser console
shows it. **Fixed** in `293278b` by allowing the two named origins (no wildcard, no
`unsafe-inline`; the new test asserts those absences too). Self-hosting the face is a
better end state — see R4.

#### M2 — `sqlparse 0.5.5`: four advisories — **FIXED**

`PYSEC-2026-3696/3697/3698/3699`, all fixed in 0.6.0 (§2.8). Reachability here is
~nil (transitive Django dep used for `sqlformat`; no attacker-controlled SQL text
reaches it). Bumped anyway in `d52563e`; `pip-audit` now reports clean.

#### M3 — `robots.txt` advertised the admin path — **FIXED**

`templates/robots.txt` shipped `Disallow: /admin/`, directly contradicting
`middleware.py`'s own stated goal ("everyone else gets a 404 so the admin's existence
is not advertised"). **Fixed** in `3da631b`: the line is gone and admin responses
carry `X-Robots-Tag: noindex, nofollow` instead — crawlers stay out without the path
being published. The rationale lives in `middleware.py`, not in `robots.txt`, since a
comment there would be served to the same scrapers.

#### M4 — CSRF was entirely unverified by the test suite — **FIXED**

Every POST test used the default Django test client, which **disables** CSRF checks.
The suite proved both forms *accept* a POST and nothing anywhere proved they *reject*
one without a token. A change dropping `CsrfViewMiddleware`, adding `@csrf_exempt`, or
loosening `CSRF_TRUSTED_ORIGINS` would have gone green.

Manual testing found **no actual bypass** (§2.1) — this is a false-confidence finding,
not a live hole. `91394f1` adds `Client(enforce_csrf_checks=True)` classes for both
forms covering the full manual matrix, plus the honeypot path (that short-circuit
lives inside the view, so it must not be a token-free route to a 302).

#### M5 — A per-IP limiter is the wrong shape for the threat — **OPEN, accepted**

3 posts/minute keyed on a single IP stops one noisy client. It does not stop a
botnet, an open-proxy list, or a single host with an IPv6 `/64` (2⁶⁴ source
addresses, each its own bucket). The honeypot is doing most of the real anti-spam
work. Reasonable for a personal site, but LOG.md's framing implies more coverage than
per-IP counting can deliver. Follow-up options in R2.

### LOW

| # | Finding | Location | Status |
|---|---------|----------|--------|
| **L1** | `/admin` without the trailing slash skipped the allowlist entirely — `CommonMiddleware` 301'd it to `/admin/`, confirming the admin exists to a client the allowlist was hiding it from | `middleware.py:61` | **FIXED** `3da631b` |
| **L2** | `/static/admin/css/base.css` returns 200 regardless of the allowlist, so the admin's existence is still inferable | middleware sits after WhiteNoise for static | **OPEN** — see R3 |
| **L3** | The login limiter counted *successful* logins, so four sign-ins in a minute locked the owner out (verified: 4th correct login → 429) | `middleware.py:65-71` | **FIXED** `3da631b` |
| **L4** | `is_rate_limited` wrote to the DB cache on *every* call, so an already-blocked flood still cost one SQLite write per request | `ratelimit.py:54` | **FIXED** `3da631b` |
| **L5** | Invalid-form and honeypot POSTs are entirely unmetered (verified: 10 of each, then a valid post still succeeds). Correct for spam — an invalid submission must not burn a real visitor's budget — but it means the endpoint itself has no ceiling | `contactme/views.py:17-23` | **OPEN**, accepted |
| **L6** | `script-src` allows *all* of `cdn.jsdelivr.net` plus `'unsafe-eval'`. jsdelivr will serve arbitrary JS from any npm/GitHub package, so "script-src blocks the primary XSS vector" is weaker than LOG.md states. Both injection sinks (`post.body\|safe` in `post_detail.html:10`, `{{ skill.url }}` in `href`) are admin-authored, so there is no visitor-reachable chain | `settings.py:306`, `post_detail.html:10` | **OPEN** — see R5 |
| **L7** | `home.MyModel` is an empty leftover model (`class MyModel: pass`) with a live `home_mymodel` table | `home/models.py:5-6` | **OPEN**, cosmetic |
| **L8** | Contact rate-limit responses are `200` with an error message rather than `429`, so automated clients cannot tell they were throttled | `contactme/views.py:24-25` | **OPEN**, cosmetic |
| **L9** | `SECURE_HSTS_PRELOAD` defaults True *with* `includeSubDomains` on the apex. Header-only, nothing auto-submitted — but if `mslevin.dev` is ever submitted to the preload list, every future subdomain is HTTPS-only and removal takes months | `settings.py:326-331` | **OPEN**, deliberate |
| **L10** | `/contactme/` and `/blog/` are each routed twice — once via `home/urls.py:9-10` and once via the project `urls.py:43-44` includes. `home.urls` wins (it is included first). Functional but confusing; a future edit to `contactme/urls.py` would silently not take effect for `/contactme/` | `home/urls.py`, `PersonalHomePage/urls.py` | **OPEN**, cosmetic |

### INFO / verified-good

- **I1** — `DATABASE_PATH` is an undocumented hard requirement: unset, `NAME` falls
  back to `/app/db.sqlite3`, `/app` is root-owned by design, and the image dies with
  `OperationalError: unable to open database file`. Correct fail-closed behaviour;
  should be stated in `.env.example` as required-for-Docker, not optional.
- **I2** — `X-Forwarded-Host: healthcheck.railway.app` is accepted (it is in
  `ALLOWED_HOSTS`). No impact: there is no link generation, no password-reset mail,
  and no cache in front, so there is nothing to poison.
- **I3** — WhiteNoise sets `Access-Control-Allow-Origin: *` on static assets. They are
  public files; no cookies or credentials are involved.
- **I4** — **Positive result:** `DJANGO_TEST=1` leaking into a production env is caught
  by the release gate (W008/W012/W016 → boot refused). The `TESTING` escape hatch in
  `settings.py:362-374` cannot silently disable secure cookies in production.
- **I5** — **Positive result:** the honeypot is implemented well. `.hp` uses off-screen
  positioning (`left: -10000px`), not `display: none` — the latter is trivially
  detected by bots. With `aria-hidden="true"` + `tabindex="-1"` it is skipped by both
  screen readers and keyboard tab order. No a11y or effectiveness issue.
- **I6** — **Positive result:** migrations reviewed and safe. `blog/0003` back-fills
  `approved=True` only for comments that predate moderation (they were already
  public — hiding them would have been a silent content change) with a `noop` reverse;
  `blog/0004` and `contactme/0003` are clean model deletions.

### LOG.md claims vs. code reality

Checked every claim in the 2026-08-20 section. Almost all hold — the Docker privilege
drop, moderation queue, PII-elimination, shared DatabaseCache limiter, header/cookie
posture and release gate are all real and were re-verified independently (§1.7, §1.8,
§2.7). Three overclaims:

1. **"Contact flow with real CSRF"** — the *suite* had zero CSRF coverage (M4). The
   manual check was real and passed; the automation did not exist.
2. **"Headless Chrome on /about under the enforced CSP: ... no CSP violations"** —
   there was a CSP violation on `/about` and on every other page (M1). Verifying a
   single page against a header-shaped expectation missed a site-wide breakage.
3. **"X-Forwarded-For is consulted only when TRUST_PROXY is on, and only its RIGHTMOST
   entry ... is used"** — accurate as written, but presented as if it closed the
   spoofing question. It closes *ordering* within the header and never asks whether
   the header should be believed at all (H1). The accompanying test pinned the wrong
   configuration.

The pattern is the same in all three: the claim describes what was *intended*, and the
verification was scoped to confirm the intent rather than to falsify it.

---

## 4. Fixes landed on this branch

Five commits on `salvage/railway-hardening`, each with its own adversarial-review note:

| Commit | Change |
|--------|--------|
| `3da631b` | **H1/L1/L3/L4/M3** — `TRUSTED_PROXY_IPS` peer check for the admin allowlist; bare `/admin` covered; `X-Robots-Tag: noindex` + `robots.txt` no longer names the path; failed-logins-only throttle; no cache write on blocked requests |
| `dfaca49` | **H2** — blank boolean env var means "unset", not False; `DeployGateTests` pin the gate in both directions |
| `293278b` | **M1** — CSP allows the two Google Fonts origins the stylesheet needs |
| `d52563e` | **M2** — `sqlparse` 0.6.0 |
| `91394f1` | **M4** — CSRF enforcement tests for both forms; comment autoescaping and mass-assignment tests |

**Test suite: 40 → 68 tests.**

### Post-fix re-verification (rebuilt image `pow-audit:fixed`)

```
H1  allowlist=203.0.113.7, peer NOT a trusted proxy
      no XFF                              404   (was 404)
      XFF: 203.0.113.7                    404   (was 200 BYPASS)
      XFF: 1.1.1.1, 203.0.113.7           404   (was 200 BYPASS)
      XFF: 203.0.113.7, 203.0.113.7       404
      bare /admin                         404   (was 301 LEAK)
      public /                            200
    log: "Ignoring X-Forwarded-For ... peer 172.17.0.1 is not in TRUSTED_PROXY_IPS"

    positive path (trusted private peer, default TRUSTED_PROXY_IPS) -- the real deploy:
      XFF: 1.1.1.1, 203.0.113.7           200   <- allowlisted client still gets in
      XFF: 203.0.113.7, 8.8.8.8           404   <- forged entry left of the real one still loses
      X-Robots-Tag: noindex, nofollow

L3  5 CORRECT admin logins in one minute   302 302 302 302 302   (was 429 on the 4th)
    5 WRONG   admin logins                 200 200 200 429 429

H2  blank TRUST_PROXY/SECURE_SSL_REDIRECT/SECURE_HSTS_PRELOAD  ->  container state: running
      Strict-Transport-Security: max-age=31536000; includeSubDomains; preload

M1  headless Chrome, all six public pages  ->  csp violations: none
    alpine=true, every x-data initialized, x-cloak-left=0, accordion still toggles
    admin (7 pages incl. changelist/filters/add-form)  ->  csp violations: none

M2  pip-audit -r requirements.txt  ->  No known vulnerabilities found

regression: rotating spoofed XFF through the edge   0:sent 1:sent 2:sent 3:LIM 4:LIM 5:LIM
            40 parallel comment POSTs               {302: 3, 200: 37}, 3 created, 0 "database is locked"
            check --deploy inside the image         no issues, exit 0
            PID 1 = appuser, /app unwritable, su-exec root denied
            all 15 public paths                     200/404 as expected
            full suite                              68 tests, OK
```

Mutation check on the new escaping tests: adding `|safe` back to `comment.body` and
`comment.author` in `post_detail.html` makes `CommentEscapingTests` fail, so the
assertions bite rather than passing vacuously.

---

## 5. Residual risks

- **R1 — H1's fix still rests on one assumption, just a much weaker one.** It now
  assumes the edge reaches the container from a private/loopback address (true for
  Railway and every comparable platform) rather than assuming every
  `X-Forwarded-For` was appended by a proxy. Anything already *inside* the private
  network can still spoof. There is no way to do better without knowing the edge's
  address — which is what `TRUSTED_PROXY_IPS` is for. **If Matt sets
  `ADMIN_IP_ALLOWLIST` and then 404s himself**, the fix is in the logs: grep for
  `not in TRUSTED_PROXY_IPS` and put the logged peer in `TRUSTED_PROXY_IPS`.
- **R2 — Spam ceiling.** M5. If spam becomes real, the cheap next steps are a global
  (not per-IP) daily cap on outbound contact mail and grouping IPv6 sources by `/64`
  instead of by exact address.
- **R3 — L2.** `/static/admin/*` still reveals that a Django admin exists. Fixing it
  means moving the allowlist ahead of WhiteNoise or blocking that prefix explicitly;
  the disclosure is worth ~nothing (`/admin/` is the Django default anyway) so it is
  left alone deliberately.
- **R4 — Third-party asset origins.** The site now depends on `cdn.jsdelivr.net`
  (Alpine, pinned + SRI) and `fonts.googleapis.com`/`fonts.gstatic.com` (Roboto, not
  pinned — there is no SRI for a stylesheet that redirects to font files). Self-hosting
  both would remove three external origins from the CSP, remove a third-party request
  per visitor, and let `script-src`/`style-src` drop to `'self'`. Recommended, but it
  changes what ships in the image, so it is a separate change, not an audit fix.
- **R5 — L6.** `'unsafe-eval'` + whole-of-jsdelivr is a genuine CSP weakening. It only
  matters if an admin-authored sink is ever fed untrusted content. If blog post bodies
  ever accept anything but Matt's own writing, `post.body|safe` must be replaced with
  a sanitiser (bleach/nh3) *first*.
- **R6 — SECRET_KEY rotation.** Out of scope for code, but `main`'s history still
  contains the old `.env` (`7b0fd2b`). Anything that was in it must be treated as
  burned. Unchanged from LOG.md; restated because it is the largest open risk on this
  project and it is not fixable inside this branch.
- **R7 — Unexercised in production conditions.** SMTP was never exercised against real
  Gmail (console/locmem backends throughout), the Railway volume was simulated with a
  bind mount, and Railway's actual `X-Forwarded-For` behaviour is assumed, not
  observed. First deploy should confirm: a real contact email arrives, `/admin/` is
  reachable with the allowlist set, and the logs are free of
  `not in TRUSTED_PROXY_IPS`.

---

## 6. Verdict

### Ready for Railway deploy (code-side): **YES — conditionally**

Everything gating that verdict is now green: no CRITICAL findings; both HIGH findings
are fixed and re-verified against a rebuilt image; the suite is 68 tests and passes;
`check --deploy --fail-level WARNING` passes inside the running container; the
privilege drop, moderation gate, CSRF enforcement, header posture, host-header
handling and SQLite behaviour under concurrency all hold under attack.

The conditions, in order of importance:

1. **`SECRET_KEY` must be freshly generated**, not carried from `main`'s history.
2. **`DATABASE_PATH` must be set** to the mounted volume (e.g. `/data/db.sqlite3`).
   The image intentionally will not boot without it (I1).
3. **After the first deploy, check the logs for `not in TRUSTED_PROXY_IPS`.** If
   Railway's edge reaches the container from a private address — which is what the
   §4 `pow-allow3` run simulates, and the expected case — the allowlist just works
   and that line never appears. It only fires if the edge peer is outside the
   default private ranges, and *then* the allowlist fails closed (Matt locked out)
   rather than open. Safe direction, but it needs to be noticed: the fix is to put
   the logged peer address into `TRUSTED_PROXY_IPS`. Do not set it pre-emptively —
   a wrong value is how you'd cause the lockout you were trying to avoid.
4. **`ADMIN_IP_ALLOWLIST` is worth setting now that it actually holds.** Before this
   audit it was bypassable with a single header (H1); it is a real control now.

Had this been reviewed before the fixes, the verdict would have been **no** — H2 alone
crashloops the container on the documented configuration, and H1 makes the branch's
headline admin control ineffective.

### What I could not verify from here

Railway's actual `X-Forwarded-For` and peer-address behaviour, real Gmail SMTP
delivery, real volume semantics, and DNS/TLS for `mslevin.dev`. Each is flagged in R7
with the specific thing to look at on first deploy.

---

*Independent adversarial review by Claude Code (opus) under AGENTS.md, 2026-08-20.
Every command and output above was run against the actual branch — findings marked
FIXED were re-run against a rebuilt image after the fix.*
