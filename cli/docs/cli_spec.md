# Knowledge Map Tool CLI

## Inputs

- Folder of markdown files

### Folder of markdown files

- e.g. an Obsidian vault

## Output

- Kuzu 0.11.x file

## Algorithm

```
for each markdown file in crawl(input_folder):
  source = fetchSource(file.path)
  if source:
    hash = hash(file.content)
    if source.hash == hash:
      skip
    else:
      deleteSource(source)
  addSource(file)

func deleteSource(source):
  deleteNode(source)
  deleteNode(source.chunks)
  deleteNode(floating observations)
  deleteNode(floating entities)

func deleteNode(node):
  execute cypher MATCH (n) WHERE n.id = node.id DETACH DELETE n statement on the kuzu database file at default.kz

func addSource(file):
  source_id = `Source:{file.path}`
  createNode(Source, {id: source_id, label: file.name, path: file.path, created_at: file.created_at, updated_at: file.updated_at, content_hash: file.content_hash, meta: {}})
  content = parse(file.content)
  chunks = chunk(content)
  for chunk in chunks:
    chunk_id = `Chunk:{file.path}:{chunk.index}`
    createNode(Chunk, {id: chunk_id, source_id: source_id, content: chunk.content, index: chunk.index, meta: {}})
    createEdge(SOURCE_CHUNK, {from: source_id, to: chunk_id})
    observations = extractObservations(chunk.content)
    for observation in observations:
      observation_id = `Observation:{observation.content}:{observation.relationship}`
      createNode(Observation, {id: observation_id, content: observation.content, relationship: observation.relationship, meta: {}})
      createEdge(CHUNK_OBSERVATION, {from: chunk_id, to: observation_id})
      for entity in observation.entities:
        entity_id = `Entity:{entity.category}:{entity.label}`
        createNode(Entity, {id: entity_id, label: entity.label, category: entity.category, meta: {}})
        createEdge(OBSERVATION_ENTITY, {from: observation_id, to: entity_id})

func extractObservations(content):
  use llm structured outputs to extract a list of observations with fields
  - content (Alice knew Bob from college)
  - relationship (knows)
  - entities (Alice:Person, Bob:Person)

func createNode(node):
  execute cypher CREATE statement on the kuzu database file at default.kz

func addEdge(from, to):
  execute cypher CREATE statement on the kuzu database file at default.kz
```

## Schema

```
CREATE NODE TABLE IF NOT EXISTS Source (
	id STRING PRIMARY KEY,
	label STRING,
	path STRING,
	created_at TIMESTAMP,
	updated_at TIMESTAMP,
	content_hash STRING,
	meta JSON
)
CREATE NODE TABLE IF NOT EXISTS Chunk (
	id STRING PRIMARY KEY,
	source_id STRING,
	content STRING,
	index INT64,
	meta JSON
)
CREATE NODE TABLE IF NOT EXISTS Entity (
	id STRING PRIMARY KEY,
	label STRING,
	category STRING,
	meta JSON
)
CREATE NODE TABLE IF NOT EXISTS Observation (
	id STRING PRIMARY KEY,
	content STRING,
	relationship STRING,
	meta JSON
)

CREATE REL TABLE IF NOT EXISTS SOURCE_CHUNK(
	FROM Source TO Chunk,
	meta JSON
);
CREATE REL TABLE IF NOT EXISTS CHUNK_OBSERVATION(
	FROM Chunk TO Observation,
	meta JSON
);
CREATE REL TABLE IF NOT EXISTS OBSERVATION_ENTITY(
	FROM Observation TO Entity,
	meta JSON
);
CREATE REL TABLE IF NOT EXISTS ENTITY_ENTITY(
	FROM Entity TO Entity,
	meta JSON
);
```

## Node IDs

- Source: `Source:{path}`
- Chunk: `Chunk:{source_id}:{index}`
- Entity: `Entity:{category}:{label}`
- Observation: `Observation:{content}:{relationship}`

## Concurrency

- Use asyncio to implement concurrency.

## Kuzu

- Use the kuzu library to execute cypher statements on the kuzu database file at default.kz

### TIMESTAMP

```
TIMESTAMP combines date and a time (hour, minute, second, and/or millisecond) and is formatted according to the ISO-8601 format (YYYY-MM-DD hh:mm:ss[.zzzzzz][+-TT[:tt]]), which specifies the date (YYYY-MM-DD), time (hh:mm:ss[.zzzzzz]) and a timezone offset [+-TT[:tt]]. Only the date section is mandatory. If the time is specified, then the millisecond [.zzzzzz] is left out. The default timezone is UTC, and Kuzu stores the timestamp based on the timezone offset relative to UTC.

// Midnight in UTC-10
kuzu> RETURN timestamp("1970-01-01 00:00:00-10") as x;

Binder exception: Expression $created_at has data type STRING but expected TIMESTAMP. Implicit cast is not supported.
Fix: use timestamp() function.
```

## LLM

- Write an LLM client for OpenAI chat completions with structured outputs.

## LLM Request Caching

- Use httpx and httpx-cache FileCache to implement request caching. e.g. `httpx_cache.Client(cache=httpx_cache.FileCache())`

## Chunking

Use Chonkie library to implement chunking.