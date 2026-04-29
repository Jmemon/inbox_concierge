

### API server
python fastapi

gmail auth


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

