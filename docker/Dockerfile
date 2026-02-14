FROM neo4j:5.18

ENV NEO4J_AUTH=neo4j/password \
    NEO4J_dbms_memory_heap_initial__size=1G \
    NEO4J_dbms_memory_heap_max__size=1G \
    NEO4J_dbms_memory_pagecache_size=512M \
    NEO4J_PLUGINS='["apoc"]' \
    NEO4J_dbms_security_procedures_unrestricted=apoc.* \
    NEO4J_dbms_security_procedures_allowlist=apoc.*

EXPOSE 7474 7687

WORKDIR /data

CMD ["neo4j"]
