## Frontend
React

### login
Select email.
if already authorized for device, go to home, else go to auth.

### auth
initiate google oauth 2.0 flow, happens on backend.
should give app access to read their emails. And to make it easy for them to login in the future via session cookie.

### Home
email homepage
50 emails at a time.
table list.
each list item is a thread, displayed with header (from-list, subject, body-preview).

### State
inbox representation.
On load pull down most recently active 200 threads and group them into four pages. this will be the first four pages in the UI.
If they go to the fifth page, request to api server for next 50 threads.
If receive an sse event with new/udpated thread ids, request the current state of those threads from backend for display if the user navigates to the page containing those threads or if they are on one of those pages.

