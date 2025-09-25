# Here we record all the improvements planned

## Working on


## To Do


### Save chunk to improve cache

### Meta won't trigger llm process

### New repo, prepare open-source 
Create a new repo: obsidian-knowledgegraph on kineviz, opensource, invite collaboration

### In GraphXR Sandbox, let user config LLM

## Finished

### Speed up meta matching  2025-09-20
Before: for each node we scan all files. slow.   
Now: batch search. improve almost 100x


### Speed up DB building  2025-09-20
Before, build reference edge one by one   
Now, batch. Improved almost 500x 

### Use .env for vault path 2025-09-20
Right now we have vault path in both .env and docker-compose.yaml, consolidate them into just use .env
