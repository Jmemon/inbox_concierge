
## Flows
### First time user opens app
authenticate their g-suite account.
pull down 200 most recently active threads to backend, classified, send down to client. 

### Nth time user opens app
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

api server
worker service
redis service (job queue + pub/sub)
postgres service


railway deployment

