# AGENTS.md — PersonalOpenSourceWebsite Standing Rules

This repo is Matt's personal portfolio (mslevin.dev). Small Django 6 + SQLite + WhiteNoise site. Goal: production-hardened, secure, simple, and actually useful as a public identity signal.

## Core Principles (non-negotiable)

1. **Security first, always**
   - Never commit secrets, `.env`, or PII.
   - Validate + sanitize every input (forms, query params, headers).
   - Rate limit all mutating endpoints (contact, comments).
   - Prefer explicit allowlists over denylists.
   - Run `manage.py check --deploy` and address every warning before any prod push.
   - Headers: HSTS, CSP (report-only first if needed), X-Content-Type-Options, Referrer-Policy, X-Frame-Options, Secure cookies, SameSite.
   - No hardcoded credentials, superuser, or debug=True in images.

2. **Test everything you touch**
   - Write or extend integration tests for every feature/fix.
   - Browser verification required for UI flows, forms, responsive behavior, and security headers (use curl + browser devtools or a headless runner).
   - Adversarial self-review: after your changes, actively try to break them (SQLi, XSS, rate-limit bypass, header spoofing, media path traversal, etc.). Document what you tried and that it failed.
   - Prefer real browser smoke + automated tests over "it looks good in my head".

3. **Write it down**
   - No mental notes. Update LOG.md, commit messages, or this file with decisions, tradeoffs, and "why".
   - Every PR or major change gets a short "Adversarial Review" section in the commit or a linked note.
   - If you make a security or hardening decision, explain the threat model briefly.

4. **Small, reviewable changes**
   - One logical change per commit / small PR.
   - Run the full test + browser verification suite before asking for review or opening PR.
   - Never leave the tree in a broken state.

5. **Production posture**
   - SQLite on a mounted volume (Railway) is the chosen path; do not fight it.
   - Media/uploads: either static or explicitly handled via volume + proper storage backend. Never rely on DEBUG static() in prod.
   - Contact/comments: decide PII policy up front (email-only vs. stored rows + retention).
   - Docker: non-root user, minimal image, no baked secrets.

6. **Adversarial mindset (your job)**
   - Before marking a task complete, spend explicit time trying to break your own implementation.
   - Common vectors for this site: contact spam, comment spam, header injection, rate-limit bypass via X-Forwarded-For, media 404s, admin exposure, email delivery failures, static file cache poisoning.
   - If you can't find a way to break it, document the attempts.

## Workflow expectations

- Start from the current branch (`salvage/railway-hardening` or whatever the active hardening branch is).
- Use the existing `entrypoint.sh`, `Dockerfile`, `railway.toml`, and `settings.py` patterns.
- When adding tests: prefer Django TestCase + LiveServerTestCase or a simple browser automation script (Playwright/puppeteer via npm if needed, or curl + assertions).
- Browser verification: at minimum, run the dev server or Docker image and manually exercise forms, check response headers with `curl -I`, inspect CSP, etc. Document the verification steps.
- Before opening a PR or declaring done: run `python manage.py check --deploy`, full test suite, and your adversarial checklist. Fix or explicitly accept every finding.

## What "done" looks like for hardening

- All P0/P1 items from the 2026-08-20 audit addressed or explicitly deferred with threat model.
- `manage.py check --deploy` clean.
- Browser + integration tests pass.
- Adversarial review documented and passed.
- No new secrets or PII in git.
- Deployable to Railway with volume + env vars only.

## Communication

When you finish a milestone or need input from Matt, send exactly one message via the notification route below. Keep it short: what was done, what was verified, any open decisions, and next step.

Notification route (use exactly this):
openclaw message send --channel matrix --target '!OEGfQLPrksesEaxHRk:levinlabs.chat' --message '<brief result>'

Do not use system events or heartbeats for completion.

## Models & tools

- Preferred: fable or opus via Claude Code.
- Always run with permission bypass only when explicitly safe; otherwise respect the tool.
- You have shell, Django manage.py, git, curl, and the ability to run the dev server or Docker image.

Follow these rules. Security and testability are the point of this exercise.