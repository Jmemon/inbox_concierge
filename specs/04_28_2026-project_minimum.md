
react frontend
- authentice g-suite account to get gmail access
- email homepage, no need to click into emails - display each email with subject line and a preview
- on initial load, group the user's last 200 threads into buckets by calling the llm-powered classification pipline


## Flows
### First time user opens app
authenticate their g-suite account.
pull down 50 most recently active threads 

### Nth time user opens app

### Creating a new custom bucket


## Frontend
React

### First-time
G-suite auth

### Home
email homepage
50 emails at a time.

## Backend


### API server
python fastapi

### job queue
redis
for classification jobs

### pub/sub
redis
for classification results

### cache
redis
user: custom buckets with criteria
questioning the need for this if we can just query postgres

### classification worker
Worker.
One job is a list of emails.
The worker can launch N classification runs at a time.
Returns all classifications.

### Postgres
#### Tables
users
email
buckets

### Blob
email headers
email bodies
email attachments

## Deployment
Railway

classification pipeline behind endpoint
Bucket service
postgresql service



llm-powered classification pipeline.
- factorable-criteria to support custom buckets/adding in arbitrary class criteria.
- is it one call per class? Or all classes in each call? Or all classes in each call until too many classes, then select topK classes to send as options to classification call? final option.
- multiple classes for an email? No.

custom buckets. users can specify new buckets that the classification pipeline can recognize. how? user describes the bucket a bit, maybe interactive back-and-forth to build bucket by surfacing old emails and asking if they belong, or if not viable (user knows no old ones would fit), maybe by producing synthetic examples that would belong in/out of bucket, having user indicate if correct (labeling some data), or having them update examples so categorizations are correct.
- name, criteria. criteria is agreed upon at bucket creation. user can create it and llm can suggest updates.
- ideally is iterated on by user feedback.

postgres table with email metadata + classifications (minimal dont need everything, KISS for this demo project) (and fk to users for each email, makes sense for consumer app, hypothetically if thinking enterprise go per-user table ie schema-per-etant). then blob storage for headers + bodies + MIME-encoded attachments.
postgres table with user info. authenticated gsuite stuff so they can login without re-authenticating. 
WHere do custom buckets + classification criteria go? postgres for bucket names linkes to user row and then maybe a key in a key-value non-relational db to a string that is teh classifciation criteria? no. classificaiotn criteria won't get so large, just include a text column in the buckets table

railway deployment
