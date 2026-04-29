
## Backend
### Postgres
#### Tables
any Ids we are copying over from gmail api, get names prepended with 'gmail_'
must support CRUD. not just adding messages/threads/users/buckets, but also deleting them, updating columns like recentMessageId and gmail_lastHistoryId. 

users
 - id: string uuid
 - email: string
 - gmail_lastHistoryId

sessions (for oauth sessions)
 - 
 - userId: fk to users.id

custom_buckets
 - id: string
 - userId: fk to users(id)
 - name: string
 - criteria: text

inbox_messages
 - id
 - userId: fk to users(id)
 - gmail_Id
 - gmail_threadId
 - gmail_internalDate
 - gmail_historyId
 - to
 - from
 - body_preview: first 100 chars (more than enough)

inbox_threads
 - userId: fk to users(id)
 - gmail_Id
 - subject
 - bucket
 - recentMessageId: fk to messages(id) of message in thread with most recent gmail_internalDate value

thread_messages (index on messages mapping actual threadIds to message sequences (using internalDate to put messages in order) for quicker access)

### Blob
I think for now we do not include this. if time at the end yes. but I believe we can trust that hte gmail api will be up when we need to pull down full message bodies and attachments. I think we store headers + body preview in postgres for hte ui view, and pull down full content when running classification.
Save us on complexity.

email headers
email bodies
email attachments







postgres table with email metadata + classifications (minimal dont need everything, KISS for this demo project) (and fk to users for each email, makes sense for consumer app, hypothetically if thinking enterprise go per-user table ie schema-per-etant). then blob storage for headers + bodies + MIME-encoded attachments.
postgres table with user info. authenticated gsuite stuff so they can login without re-authenticating. 
WHere do custom buckets + classification criteria go? postgres for bucket names linkes to user row and then maybe a key in a key-value non-relational db to a string that is teh classifciation criteria? no. classificaiotn criteria won't get so large, just include a text column in the buckets table

