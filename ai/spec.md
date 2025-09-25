Use this prompt to generate a full featured CLI tool for managing Kuzu database files (.kz) which adhere to the Knowledge Map schema. The first inspiration is to support the import of Obsidian vaults.

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
	content STRING,
	source_id STRING,
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

## Core Features

- Document Import
  - Add an Obsidian vault
  - Supported file types: PDF, DOCX, MD
- Incremental Updates / idempotency: synchronize the Knowledge Map with the Obsidian vault.
- Knowledge Mapping: define a set of rules for automatically extracting observations, entities, and relationships.
- Human in the loop: e.g. for entity resolution, the user can manually resolve the entities. Generally, background jobs will submit reports to the user which they can manually review and resolve.
- Kuzu Export: export the Knowledge Map to a Kuzu database file.
- Chunking: chunk the document into smaller chunks.
- Caching: cache the results of the LLM calls.
- No-copy: the tool avoids creating duplicates of files on the filesystem, preferring to link to the original file.
- Background Jobs: many tasks can be processed in parallel, and failures are recorded and retryable.
- Monitoring: monitor the progress and status of background jobs. Can view a history of jobs and their status.
- Entity Resolution: link together entities that are similar to each other.

## Advanced Features

- Continuous Integration: automatically update the Knowledge Map when new documents are added to the Obsidian vault, or when document content changes.
- Semantic Search: search the Knowledge Map for entities and relationships.
- Import from Notion

## Description of Features

### Knowledge Mapping

- Define a set of rules for automatically extracting observations, entities, and relationships.
- Rules can be defined in a YAML file.

### Add Source
- Input
	- Folder of documents
		- Obsidian vault
	- Individual documents
- Can specify a parsing backend: MarkItDown by default, LlamaParse optional
- Will add a Source node
- Will chunk and add Chunk nodes

### Entity Resolution

- Entity Resolution runs continously.

#### Human in the loop

- e.g. The system may report entities that are similar to each other, and the user can manually resolve them. The Resolve Entities command may also be used to manually resolve entities by submitting a patch file.

#### Potential rules for merging entities

- Entities have the same name, same type: if two entities have the same name and same type, merge them together
- Entities have similar name, same type: if two entities have the same type, and their names are similar, merge them together. Use Levenshtein distance to determine similarity.
- Entities have same name, different type: if two entities have the same name, and different types, report them to the user for manual resolution.

### Chunking

- Chunk the document into smaller chunks using a chunking strategy.

### Caching

- Cache the results of the LLM calls to save on costs and improve debuggability.

### Continuous Integration

- Automatically update the Knowledge Map when new documents are added to the Obsidian vault.

#### Automatically importing new documents

- Can use `entr` to monitor the Obsidian vault for changes and then run the update.
- Can use `cron` to run the update at a regular interval.
- Create a web service that continously monitors the file system for changes and then runs the update.

#### Automatically updating existing documents

- When document content changes, update the Knowledge Map.
- Algorithm for updating the Knowledge Map:
	- Remove old Chunk nodes.
	- Remove floating Observation nodes.
	- Remove floating Entity nodes.
	- Create new Chunk nodes.
	- Re-run Extraction.

### Background Jobs

- Many tasks can be processed in parallel, and failures are recorded and retryable.
- Can view the status of background jobs.
- Can cancel background jobs.
- Can retry background jobs.
- Can view the history of background jobs.
- Temporal?

### Semantic Search

- Search the Knowledge Map for entities and relationships.
- Convention for indexing node table X:
	- Create a new node table `XYVector` with `id STRING PRIMARY KEY` and `vector FLOAT[384]` properties, where `id` is the `id` of the node, where `X` is the name of the node table, and `Y` is the name of the property to index, like `content` or `label`.
	- Add vector index `XYVector_index`
	- Add rel table `X_Y_VECTOR` from `X` to `XYVector`

## Useful Python Libraries

- pyinstaller (for packaging into a binary)
- Python RQ (Simple Job Queue)
- Temporal (Durable Workflows)
- Typer (CLI)
- Textual (TUI)
- Rich

## Notes

- Needs to be easy enough for Tiby, Wei, and Lightbridge to install and use.
- Needs to be in a language that Wei and Dienert are comfortable with.

# Roadmap

1. (you are here) Basic CLI with manual invocation via commands. All Core Features.
2. Service with web interface. Continuous Integration.