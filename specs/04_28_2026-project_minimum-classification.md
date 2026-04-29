

## workers
### factorable functionality
threadId(s) -> pull down, parse, assemble -> threadString(s)
threadString(s) -> llm-powered classification -> thread buckets
threadId(s) -> get threads -> thread objects

### worker: partial_sync_inbox 
input: userId


get gmail_lastHistoryId from postgres
call users.history.list endpoint with that id.
 - history records contain message adds and deletes in the form of thread and message Ids. 

First go through messageDeletes and any messages that were deleted that are currently in inbox_messages, delete their rows (and potentially updates threads recentMessageId if that one got deleted and thread_messages, and users.gmail_lastHistoryId potentially).
 - realistically won't deal with this for this project
From messagesAdded, get message and thread Ids.

Pull down the full threads containing the new messages (either new or already seen)
Parse the threads (Message parser + thread assembler) into a string representation
 - include headers, bodies, and attachments
Run each through classification pipeline
CRUD postgres with:
 - new gmail_lastHistoryId
 - new message data for messages table
 - new thread data for threads table
 - changes to existing threads rows (ie different bucket)

publish list of new/updated thread Ids to pub/sub channel for job.

### worker: full_sync_inbox
input: userId. 
that's enough to call the google api to get hte threads using <what oauth token?> and their userId.

pull down most recently active 200 threads
Parse the threads (message parser + thread assembler) into a string representation
 - include headers, bodies, and attachments
Run each through classification pipeline
If user has threads in postgres means lastHistoryId was old so had to do full sync:
 - easy option: throw out what was in there and then proceed to the "user has no threads in postgres" case. 
 - more challenging option: reconcile. would have to account for messages deleted and added. naively I'm imagining reconstructing the history records from a diff between newest 200 most recent and whatever is in the database as the 200 most recently active threads.
 - let's do easy for this.
If user has no threads in postgres:
 - write rows for every thread and message into inbox_messages and inbox_threads
 - update users.gmail_lastHistoryId with most recent message's historyId

publish done notification to pub/sub channel for job.


### job queue
redis underlying, interace with celery

partial_sync_inbox(userId, newHistoryRecords)
full_sync_inbox(userId)

### pub/sub
redis
for sync results

### cache
redis
user: custom buckets with criteria
questioning the need for this if we can just query postgres

### classification worker
Worker.
One job is a list of threads to classify.
The worker can launch N classification runs at a time. Each run is for a whole thread.
Returns all classifications.






llm-powered classification pipeline.
- factorable-criteria to support custom buckets/adding in arbitrary class criteria.
- is it one call per class? Or all classes in each call? Or all classes in each call until too many classes, then select topK classes to send as options to classification call? final option.
- multiple classes for an email? No.

custom buckets. users can specify new buckets that the classification pipeline can recognize. how? user describes the bucket a bit, maybe interactive back-and-forth to build bucket by surfacing old emails and asking if they belong, or if not viable (user knows no old ones would fit), maybe by producing synthetic examples that would belong in/out of bucket, having user indicate if correct (labeling some data), or having them update examples so categorizations are correct.
- name, criteria. criteria is agreed upon at bucket creation. user can create it and llm can suggest updates.
- ideally is iterated on by user feedback.

