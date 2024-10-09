from pprint import pprint
from mapknowledge import KnowledgeStore
import json

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)

    store = KnowledgeStore(sckan_version='sckan-2024-09-21')

    print('Paths without disconnected and empty connectivity:', len(store.connectivity_paths()))
    print('Paths with disconnected and empty connectivity:', len(store.connectivity_paths(connected_only=False)))
    print('Disconnected paths:')
    pprint({path:f"{len(store.entity_knowledge(path)['connectivity'])} edge/s"
            for path in set(store.connectivity_paths(connected_only=False))-set(store.connectivity_paths())})

    # store extracted knowledge to JSON file
    json_file = f'sckan/{store.source}.json'
    with open(json_file, 'w') as f:
        json.dump(store.extract_knowledge(), f, indent=4)
