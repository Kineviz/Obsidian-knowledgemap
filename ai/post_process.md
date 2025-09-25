### Merge Entities

```
CREATE NODE TABLE MergedEntity (
  id STRING PRIMARY KEY,
  category STRING,
  label STRING
);

CREATE REL TABLE DEFINED_IN(FROM MergedEntity TO Entity);

MATCH (e:Entity)
MERGE (ne:MergedEntity {id: e.category + ':' + e.label, category: e.category, label: e.label})
MERGE (ne)-[:DEFINED_IN]-(e);

CREATE REL TABLE HAS_OBSERVATION(FROM MergedEntity TO Observation);

MATCH (ne:MergedEntity)-[:DEFINED_IN]-(e:Entity)-[:OBSERVATION_ENTITY]-(o:Observation)
MERGE (ne)-[:HAS_OBSERVATION]->(O)

CREATE REL TABLE RELATED(FROM MergedEntity TO MergedEntity);

MATCH (e0:MergedEntity)-[:HAS_OBSERVATION]->(O:Observation)<-[:HAS_OBSERVATION]-(e1:MergedEntity)
WHERE e0<>e1
MERGE (e0)-[:RELATED]->(e1)

```