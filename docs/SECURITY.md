# Security checklist — What's Cooking?

Audited against [The Vibe-Coded App Security Checklist (25 items)](https://vibeaudits.com/blog/vibe-coded-app-security-checklist)
on Nov 21, 2026. ✅ done (with evidence) · ➖ not applicable (and why). Tests live in `backend/tests/test_security.py`
unless noted; the live checks were run against the production site after deploy.

## Secrets & credentials
| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | No hard-coded secrets (incl. git history) | ✅ | Pattern scan of tracked files and full `git log -p` (OpenAI/Google/OAuth/Render/HF/Neon/private-key/DB-URL patterns) = 0 hits; every key ever pasted in development checked against history = clean |
| 2 | No secrets in client code | ✅ | Only `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_SHIPPING` reach the browser |
| 3 | Env vars set in every environment | ✅ | Render production has all 13 required keys; the API **refuses to start** in production without `APP_SECRET` (`test_production_cors_and_secret`) |
| 4 | `.env` files ignored | ✅ | `.gitignore` covers `.env` and `.env.*`; only blank `.env.example` templates are tracked |

## Authentication
| # | Item | Status | Evidence |
|---|---|---|---|
| 5 | Passwords hashed (bcrypt/argon2/scrypt) | ➖ | No passwords: sign-in is Google only |
| 6 | Sessions expire | ✅ | Sign-in session 90 days (`accounts.SESSION_DAYS`); YouTube connections now expire after 90 days too (`test_youtube_connection_expires`) |
| 7 | Signing secrets strong | ✅ | `APP_SECRET` is a random 32-byte Fernet key; the OAuth-state HMAC no longer falls back to a weak default |
| 8 | Reset tokens expire / single-use | ➖ | No passwords, no reset flow |
| 9 | Email verification enforced | ✅ | Google accounts only; an email is stored only if Google says it's verified, and no feature is gated on email |
| 10 | OAuth `state` validated | ✅ | Server-signed HMAC state with a 15-minute expiry, plus a browser nonce the page must match (stops login/connection CSRF); `test_youtube_connect_carries_browser_nonce`, sign-in nonce browser test |

## Authorization
| # | Item | Status | Evidence |
|---|---|---|---|
| 11 | Every route checks the caller | ✅ | `test_every_route_was_reviewed` lists all 36 routes with who may call them and fails if a new route isn't reviewed |
| 12 | Users only reach their own data | ✅ | By-id routes 404 across studios (`test_studios_cannot_reach_each_others_jobs_and_videos`, director/mascot tests); live: a fresh studio gets 404 for another studio's job/video/retry |
| 13 | Admin routes admin-only | ✅ | `GET` and `PATCH /settings` need `X-Admin-Token` (`test_settings_are_admin_only`) |
| 14 | Tenant boundaries enforced server-side | ✅ | The studio comes from the server-verified session/browser id (`db.current_restaurant`), every query filters by it; no client-side filtering. (Not Postgres RLS: the database is only reachable by the API server.) |

## Input validation
| # | Item | Status | Evidence |
|---|---|---|---|
| 15 | Parameterized queries | ✅ | SQLModel/SQLAlchemy everywhere; the one f-string SQL is a fixed internal migration list |
| 16 | Uploads restricted by type and size | ✅ | Server-side: 10 MB, JPG/PNG/WEBP decoded by Pillow (not trusted from the header), CSV 5 MB; new: images over 40 MP refused (decompression bombs, `test_decompression_bomb_is_refused`); 40 uploads/hour per visitor |
| 17 | User input escaped before rendering | ✅ | React escapes; no `dangerouslySetInnerHTML`; captions burned into video have formatting codes stripped (`render._ass_text`) |

## Rate limiting
| # | Item | Status | Evidence |
|---|---|---|---|
| 18 | Login rate-limited | ✅ | Google sign-in start + callback: 30/hour per visitor (`test_sign_in_is_rate_limited`); Google itself handles password attempts |
| 19 | Password reset rate-limited | ➖ | No reset flow |
| 20 | AI endpoints have spend limits | ✅ | $10 lifetime hard cap in code (`budget.HARD_CAP_CENTS`, includes spend from before the ledger); per-visitor: 1 video in progress, 6/hour; queue cap 4; Director 60/hour per visitor + 3,000/day total; previews 10/hour + 40/day; mascots 4/hour + 15/day |

## Payments & webhooks
| # | Item | Status | Why |
|---|---|---|---|
| 21 | Stripe webhook signatures | ➖ | No payments |
| 22 | Idempotent fulfilment | ➖ | No payments |
| 23 | Subscription checked server-side | ➖ | No subscriptions (the AI budget is enforced server-side, #20) |

## Infrastructure
| # | Item | Status | Evidence |
|---|---|---|---|
| 24 | Supabase RLS | ➖ | Not Supabase. Neon Postgres is reachable only with server credentials; no browser-facing data API |
| 25 | Errors don't leak internals | ✅ | Unhandled errors return a generic message and log details server-side (`test_errors_do_not_leak_details`); YouTube upload failures no longer echo the raw exception (`test_failed_youtube_upload_does_not_leak_internals`) |

## Also fixed in this pass
- CORS: the production API no longer accepts `localhost` origins (dev only).
- Security headers on the site: X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy (earlier pass).

## Known limits (accepted for now)
- Per-visitor limits use the client IP: rotating proxies can get around them. The queue cap and the $10 hard cap
  still hold. Accounts (Google sign-in) are the base for per-account limits later.
- A guest studio is keyed by a random id in the browser: whoever has that id can open it. Sign in to tie it to an account.
- No Content-Security-Policy header yet (planned; needs careful allow-listing of the API, media and Google sign-in).
