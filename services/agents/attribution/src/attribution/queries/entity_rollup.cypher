// params: $case_id
MATCH (e:Entity {case_id: $case_id})<-[:CONTROLLED_BY]-(t:Trader)
OPTIONAL MATCH (t)-[:ROUTED_THROUGH]->(b:Broker)
OPTIONAL MATCH (t)-[:USES_DEVICE]->(d:Device)
RETURN e.entity_id AS entity_id, e.ring_score AS ring_score,
       collect(DISTINCT t.account_id) AS accounts,
       collect(DISTINCT b.broker_id)  AS brokers,
       count(DISTINCT d)              AS devices;
