
### Postgres

> the users table (incl gmail oauth token columns) and the sessions table are defined in the auth spec. tables below are the inbox/bucket data model.

#### Tables
any Ids we are copying over from gmail api, get names prepended with 'gmail_'
must support CRUD. not just adding messages/threads/users/buckets, but also deleting them, updating columns like recentMessageId and gmail_lastHistoryId.

note: users.gmail_lastHistoryId (defined alongside the rest of users in the auth spec) is the sync cursor — read/written by the partial/full sync workers.

buckets
 - id: string
 - userId: nullable fk to users(id) // null if a default bucket
 - name: string
 - criteria: text

buckets_userId_index - index on buckets by userId so we can quickly get user's custom buckets as well as quickly get the default buckets (for null userId)

inbox_messages
 - id
 - threadId: fk to inbox_threads(id)
 - userId: fk to users(id)
 - gmail_Id
 - gmail_threadId
 - gmail_internalDate
 - gmail_historyId
 - to
 - from
 - body_preview: first 100 chars (more than enough)

inbox_threads
 - id
 - userId: fk to users(id)
 - gmail_Id
 - subject
 - bucketId: nullable fk to buckets
 - recentMessageId: fk to messages(id) of message in thread with most recent gmail_internalDate value

inbox_messages_threadId_index (index on inbox_messages by threadId (fk inbox_threads.id for quick thread access)

### Blob
I think for now we do not include this. if time at the end yes. but I believe we can trust that hte gmail api will be up when we need to pull down full message bodies and attachments. I think we store headers + body preview in postgres for hte ui view, and pull down full content when running classification.
Save us on complexity.

email headers
email bodies
email attachments




postgres table with email metadata + classifications (minimal dont need everything, KISS for this demo project) (and fk to users for each email, makes sense for consumer app, hypothetically if thinking enterprise go per-user table ie schema-per-etant). then blob storage for headers + bodies + MIME-encoded attachments.
WHere do custom buckets + classification criteria go? postgres for bucket names linkes to user row and then maybe a key in a key-value non-relational db to a string that is teh classifciation criteria? no. classificaiotn criteria won't get so large, just include a text column in the buckets table
