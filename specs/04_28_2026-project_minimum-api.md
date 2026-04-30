

### API server
python fastapi

### Auth endpoints
no auth required on /auth/login and /auth/callback. /auth/me and /auth/logout require session cookie.

GET /auth/login
 - 302 to google authorize URL, sets short-lived signed state cookie

GET /auth/callback?code=&state=
 - validates state, exchanges code, upserts user, creates session, sets session cookie, 302 to /
 - on ?error= from google, 302 to /?authError=<reason>

GET /auth/me
 - 200 {id, email, name} or 401

POST /auth/logout
 - 204, revokes session row + clears cookie

### Auth dependency
fastapi dependency get_current_user:
 - read session cookie -> look up sessions (not revoked, not expired) -> join users -> return user or 401
 - applied to every non-/auth endpoint
 - updates lastSeenAt as a side effect

### Static files (spa hosting)
fastapi serves the built react bundle from the same origin as the api. avoids cross-site cookie problems on railway's *.up.railway.app subdomains.
 - mount StaticFiles at /assets (hashed bundle output from bun build)
 - catch-all GET handler for non-/api, non-/auth, non-/assets paths returns index.html (so client-side routing works on refresh)
 - api routes live under /api/* (or just at root, but /api/* keeps the catch-all simple)

### Cookies
session cookie: HttpOnly, Secure (prod), SameSite=Lax, path=/
no cookie domain set on railway-issued hosts (public suffix list). only set COOKIE_DOMAIN once on a custom domain.
no CORS middleware needed in v1 since frontend + api are same-origin. add one later only if we split origins.

### Proxy headers
railway terminates tls at the edge; the container sees plain http. launch uvicorn with --proxy-headers --forwarded-allow-ips='*' so request.url.scheme reflects the public https. otherwise any code that branches on scheme (eg deciding to send Secure cookies in dev vs prod) will misbehave.

### Env
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
SESSION_SECRET (signs oauth state cookie)
SESSION_TTL_SECONDS (default 30 days)
ENCRYPTION_KEY (encrypts gmail tokens at rest. set once, never rotate casually - rotating strands every stored refresh token)
COOKIE_DOMAIN (only when on a custom domain; leave unset on railway-issued hosts)

gmail session for user:
 - userId
 - nextPageToken

open gmail session(get 200 most recently active threads, initiate a watch process so the app auto-updates with new thread activity (bts running classificatoin before sending down to client via sse)):
 - get most recently active N threads (200) using gmail api. sotre next page token
 - threads with messages stored in blob storage with metadata in psql
 - classification job:
     - if new message in an already-existing thread, add thread to classification job. (thread might go from no classification to important given new message content)
     - if new thread, add to classification job
     - if already-existing thread with no new messages, use existing classification.
 - await append job to job queue (celery) (ie wait until classifications return)
 - return classified threads unless no new activity, then just return the N threads since no job will have happened
    - threads should have headers (subject/to/from) differentiated from body since we are not enabling user to click into emails, just see header + body preview.

close gmail session
 - shut down watch process
 - clear the in-memory user stuff (next page token and anything else)

next page of threads
 - only called if client doesn't have next page. 
 - use next page token from opening user's gmail session to get next 50 most recently active threads, store new next page tokens.
 - new classification job with same logic as the open gmail session
    - ...
 - response is classified threads (unless no new activity, then just the threads)

