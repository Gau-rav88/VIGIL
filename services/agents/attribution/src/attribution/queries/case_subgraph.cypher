// params: $case_id, $max_nodes (500)
MATCH (e:Entity {case_id: $case_id})<-[:CONTROLLED_BY]-(t:Trader)
WITH collect(DISTINCT t) AS traders LIMIT 1
UNWIND traders AS a
OPTIONAL MATCH (a)-[l:LINKED {case_id: $case_id}]-(b:Trader) WHERE b IN traders
OPTIONAL MATCH (a)-[tw:TRADED_WITH]->(c:Trader) WHERE c IN traders
OPTIONAL MATCH (a)-[:USES_DEVICE]->(d:Device)
OPTIONAL MATCH (a)-[:ROUTED_THROUGH]->(br:Broker)
RETURN a, collect(DISTINCT l) AS links, collect(DISTINCT tw) AS trades,
       collect(DISTINCT d) AS devices, collect(DISTINCT br) AS brokers
LIMIT $max_nodes;
