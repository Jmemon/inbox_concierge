
## Base
You can build a web or mobile interface for this project. If you decide to build a web interface, use React. If you decide to build a mobile interface, use Expo. Through this interface, a user should be able to authenticate a G-Suite account, which should be used to give gmail access.

On load, group the user’s last 200 threads into buckets (Important, Can wait, Auto-archive, Newsletter, etc.) using an LLM-powered classification pipeline you design. You only need to show the emails with their subject lines and a preview, like the homepage of any email application. Users do not have to be able to click into the emails.

Then, allow the users to create their own buckets, outside of the default options you choose, which should then recategorize all of the emails based on the new buckets.

## My Additions
Task Buckets. Creating a task (what does user specify: terminal state eg offer-accepted + purpose of task). Some notion of task state. what does this look like for a job hunt or finding a therapist? candidates + state of interaction with each candidate. different pipeline for this(?) (flags emails as being relevant to a task, then how to update task state). Meant to be useful for something like a job-hunt, finding a therapist, working on a client contract(?).

Classification pipeline feedback loop. User flags bad classifications or pipeline surfaces uncertain cases to user for the user to classify. With enough data collected, can iterate on classifications. 
 - threads with wrong bucket user specifies, this is communicating behind the scenes
 - when viewing buckets get a selection of the threads categorized under that bucket and user can click on ones that don't belong

 with enough buckets do a topK buckets approach. embed emails and find closest K bucekts by comparing with bucket criteria embeddings. unneeded for initial version. would only need for user's with a lot of buckets, what this threshold is would be best determined empirically.
