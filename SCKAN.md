# New SCKAN release

1. [Load the new SCKAN release](#updating-sckan-knowledge) as JSON into a test `map-knowledge` environment. Commit the
   resulting `sckan/SCKAN_VERSION.json` into the `map-knowledge` repository.
2. Run `map-knowledge` tests and example code as required to verify the new SCKAN release.
3. In a test environment, [update the CQ database](#reloading-cq-database-with-sckan-knowledge).
4. Configure a test `map-server` to use the test CQ database and run its CQ tests.

## Deployment

1. Add the [new SCKAN to the staging server's knowledge store](#reloading-a-knowledge-store-with-sckan).
2. Add the [new SCKAN to the staging CQ database](#reloading-cq-database-with-sckan-knowledge).
3. Update flatmap manifests to use the new SCKAN and rebuild the maps (automatic, on push (tag??)).
4. Map knowledge in the staging CQ database will be automatically updated when a map is rebuilt.
5. At promotion time, update production databases (`mapknowledge.db` and production CQ database).
6. At promotion time, copy rebuilt maps from staging to production -- map knowledge in the production CQ database will be automatically updated.

----

## Updating SCKAN knowledge

This will save SCKAN as JSON, formatted for `map-knowldege`.

```sh
source .venv/bin/activate

python tools/sckan_connectivity.py --store-directory sckan load --sckan SCKAN_VERSION --save
```

where `SCKAN_VERSION` is the version identifier of a `sckan` release, for instance `sckan-2026-02-11`.

Commit the newly created JSON file `sckan/SCKAN_VERSION.json` into the `map-knowledge` so that it becomes
part of a release.

----

## Reloading CQ database with SCKAN knowledge

```sh
source .venv/bin/activate

export COMPETENCY_USER=xxxxxx:xxxxxxx
export COMPETENCY_DATABASE=map-knowledge   # or prod-knowledge

python tools/cq_import.py json sckan/SCKAN_VERSION.json
```

----

## Reloading a knowledge store with SCKAN

In a separate terminal window:
```sh
tmux a -t FLATMAP_SERVER_INSTANCE
^C              # Stop server
```

Then from this map knowledge directory:
```sh
source .venv/bin/activate

python tools/sckan_connectivity.py --store-directory ~/services/FLATMAP_SERVER_DIRECTORY/flatmaps restore sckan/SCKAN_VERSION.json
```

and then restart the server.

----

## Upgrading CQ database schema

```sh
source .venv/bin/activate

export COMPETENCY_USER=xxxxxx:xxxxxxx
export COMPETENCY_DATABASE=map-knowledge   # or prod-knowledge

python tools/cq_upgrade.py  --upgrade
```

----
