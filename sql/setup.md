# Setting up a new Postgres SCKAN Knowledge Store

```
$ psql -d postgres

create user abi with encrypted password 'XXX';

drop database "map-knowledge";

create database "map-knowledge" owner abi;
```

```
$ cd knowledge

$ psql -d "map-knowledge" -f sql/map-knowledge.schema.sql -U abi

$ uv sync --group tools

$ export COMPETENCY_USER=abi:XXX
$ export COMPETENCY_DATABASE=map-knowledge
$ uv run python tools/cq_upgrade.py
$ uv run python tools/cq_import.py json sckan/sckan-2026-02-11.json
```
