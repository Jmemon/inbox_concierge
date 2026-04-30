
## Flows
### Auth (oauth 2.0 + cookie session)
backend is the confidential oauth client. frontend never touches tokens.

login start (GET /auth/login)
 - generate random state, set as short-lived signed cookie (10 min ttl, signed with SESSION_SECRET)
 - 302 to google authorize URL
 - scopes: openid email profile https://www.googleapis.com/auth/gmail.readonly
 - access_type=offline, prompt=consent so we reliably get a refresh token

callback (GET /auth/callback?code=&state=)
 - verify state matches signed cookie, clear the state cookie
 - exchange code at google token endpoint for {access_token, refresh_token, expires_in}
 - call userinfo with access_token to get {email, name}
 - upsert users row by email. encrypt and persist refreshToken + accessToken + expiresAt
 - insert sessions row, set its id as session cookie (HttpOnly, Secure, SameSite=Lax)
 - 302 to / (single-origin, fastapi serves the spa at /)

session check (GET /auth/me)
 - read session cookie, look up sessions row where revokedAt is null and expiresAt > now()
 - 200 {id, email, name} or 401
 - update lastSeenAt

logout (POST /auth/logout)
 - set revokedAt on sessions row, clear cookie. 204.

token refresh
 - any backend call that needs gmail goes through a helper that checks gmail_accessTokenExpiresAt, refreshes via refreshToken if expired, persists the new access token.
 - if google returns invalid_grant on refresh: null out gmail tokens for that user. next /auth/me returns 401, frontend bounces to login.

failure modes
 - user denies consent: callback gets ?error=access_denied, 302 to /?authError=denied
 - state mismatch or missing: 400, do not exchange code
 - session expired or revoked: 401 from anything authed, frontend bounces to login

### First time user opens app
authenticate their g-suite account.
pull down 200 most recently active threads to backend, classified, send down to client. 

### Nth time user opens app
GET /auth/me succeeds (cookie still valid).
get historyId of most recent stored message for user.
use the users.history.list endpoint with this historyId to get any new messages and update threads/messages data with any new messages, if receive a 404 need to totally resync, pull down 200 most recently active threads.
 - in either case we need to run classification on any new threads or updated threads.
Otherwise if no new messages, then need to pull down all threads/messages from database/blob storage and send them down as threads in order of most recently active.

### Messages while user is logged in
DO NOT DO THIS: gmail api watch process should notify backend when new messages are received. Requires us to set up a pub/sub channel on gcp, unnecessary complexity.

Poll the users.history.list endpoint every 30 secs (or so, should be a configurable env var) using user's most recent message's historyId.
If nothing, do nothing.
If new history records create a new job in the job queue, for userId partial_sync_inbox job with the history records.
And subscribes to pub/sub channel created for that job's done notification (containing new/updated threadIds).

SSE to client with new/updated threadIds. (client will request the updated versions of threads when ready)

### Message Parser
gmail message data model: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages#Message
Important fields:
 - id: string
 - threadId: string
 - internalDate: string (int64 format)
 - historyId: string
 - payload: MessagePart

MessagePart data model: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages#messagepart
Important fields:
 - headers: Header[] 
 - body: MessagePartBody
 - parts: MessagePart[]
Generally speaking I'm guessing we will only need the top-level MessagePart, the parts field is for multipart MIME-type, which I'm guessing we don't need to worry about too much here. unless 

Header data model:
 - name: string (ie "To", "From", "Subject")
 - value: string (eg "someone@email.com")

MessagePartBody data model: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages.attachments#MessagePartBody
Important fields:
 - data: string (base64-encoded string) - I believe this is where the text will be for normal emails. in teh case of an attachment, we will ahve to use gmail api to pull down attachments as well (messages.attachments.get)
 - attachmentId: string

### Creating a new custom bucket


## Deployment
Railway

single-origin setup. fastapi serves the built react bundle as static files alongside the api routes, so frontend and api share one origin. avoids the cross-site cookie issue with railway's *.up.railway.app subdomains (they're on the public suffix list, so cross-subdomain SameSite=Lax cookies don't ride on fetch). custom domain not required for v1.

services:
 - api server (also serves the spa bundle)
 - worker service (celery, runs sync + classification jobs)
 - redis service (job queue + pub/sub)
 - postgres service

build:
 - frontend built with bun, output copied into api image (eg /app/static)
 - fastapi mounts StaticFiles for /assets and a catch-all that returns index.html for unknown non-/api paths (spa router)

runtime notes:
 - uvicorn launched with --proxy-headers --forwarded-allow-ips='*' so request.url.scheme reflects the public https (railway terminates tls at the edge)
 - bind to $PORT
 - do not set cookie domain on railway-issued hosts (public suffix list rejects it). only set COOKIE_DOMAIN once on a custom domain.
 - ENCRYPTION_KEY is set once in railway variables and never rotated casually. rotating it strands every stored gmail refresh token and forces all users to re-auth.

