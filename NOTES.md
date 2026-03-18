# map-knowledge

## Updating SCKAN NPO knowledge

This will save SCKAN as JSON, formatted for `map-knowldege`.

```sh
$ python tools/sckan_connectivity.py --store-directory sckan load --sckan sckan-2026-02-11 --save
```

## Reloading CQ database with SCKAN NPO knowledge

```sh
$ source .venv/bin/activate
$ export COMPETENCY_USER=xxxxxx:xxxxxxx
$ PYTHONPATH=. python tools/cq_import.py json sckan/sckan-2026-02-11.json
```


## New SCKAN release

1. Load updated SCKAN as JSON as above in a test `map-knowledge` environment.
2. Run `map-knowledge` tests and example code as required.
3. In a test environment, update the CQ database as above.
4. Configure a test `map-server` to use the test CQ database and run its CQ tests.
5. Update `mapknowledge.db` on servers with the new SCKAN, using the JSON version created above.
6. Add the new SCKAN to the staging CQ database (from JSON).
7. Update flatmap manifests to use the new SCKAN and rebuild the maps (automatic, on push (tag??)).
8. Map knowledge in the staging CQ database will be automatically updated when a map is rebuilt.
9. At promotion time, update production databases (`mapknowledge.db` and production CQ database).
10. At promotion time, copy rebuilt maps from staging to production -- map knowledge in the production CQ database will be automatically updated.
