## Frontend
React

### auth state
spa is served by fastapi from the same origin as the api, so all requests are same-origin and the session cookie rides along by default.
on app mount: fetch('/auth/me')
 - 200 -> store user, render home
 - 401 -> render login
 - while pending -> splash

401 from any authed call -> clear user, bounce to login.

### splash
shown while /auth/me is pending on mount, and during the post-callback redirect when we land back on / before /auth/me resolves.
full-viewport, centered. app name/logo + a subtle spinner. nothing else.

### login screen
shown when /auth/me returns 401.
full-viewport, centered card.
 - app name + one-line tagline
 - "sign in with google" button (google's brand button, white bg + colored G mark)
 - if url has ?authError=<reason>, render a small inline error above the button (eg "sign-in cancelled" for denied)
button click does window.location.assign('/auth/login'). backend handles the whole oauth dance and 302s back to / with cookie set. on return, app remounts -> /auth/me -> home.

### Home
email homepage.
top bar across the page:
 - left: app name
 - right: user's name + a small menu button. menu has "sign out".
50 emails at a time.
table list.
each list item is a thread, displayed with header (from-list, subject, body-preview).

### State
inbox representation.
On load pull down most recently active 200 threads and group them into four pages. this will be the first four pages in the UI.
If they go to the fifth page, request to api server for next 50 threads.
If receive an sse event with new/udpated thread ids, request the current state of those threads from backend for display if the user navigates to the page containing those threads or if they are on one of those pages.

### logout
"sign out" in the top-bar menu -> POST /auth/logout -> clear user -> route to login.

