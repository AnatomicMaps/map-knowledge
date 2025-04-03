#===============================================================================

from mapknowledge import KnowledgeStore
import json
import os

#===============================================================================

class PathError(Exception):
    pass

#===============================================================================

"""
This script is used to extract knowledge from a particular SCKAN release.
The results are stored as a JSON file in the specified directory.
The file name will be sckan-xxxx-xx-xx-npo.json.
"""

def extracting_knowledge(args):
    store = KnowledgeStore(sckan_version=args.sckan_version)
    
    knowledge = dict()
    for path in store.connectivity_paths():
        print(path)
        knowledge[path] = (knowledge_path := store.entity_knowledge(path))
        knowledge_path['source'] = store.source
        # extracting connectivity
        terms = [term for edge in knowledge_path['connectivity'] for term in [edge[0][0]] + list(edge[0][1]) + [edge[0][0]] + list(edge[0][1])] \
                + knowledge_path.get('phenotypes', []) + knowledge_path.get('taxons', []) \
                + [term for node in knowledge_path.get('dendrites', []) for term in [node[0]] + list(node[1])] \
                + [term for node in knowledge_path.get('axons', []) for term in [node[0]] + list(node[1])]
        for term in terms:
            if term not in knowledge:
                knowledge[term] = store.entity_knowledge(term)
                knowledge[term]['id'] = term
                knowledge[term]['source'] = store.source

    npo_knowledge = {
        'source': store.source,
        'knowledge': list(knowledge.values())
    }
    
    dest_file = os.path.join(args.output_dir, f'{store.source}.json')
    with open(dest_file, 'w') as f:
        json.dump(npo_knowledge, f, indent=4)

def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Extracting knowledge from a specific sckan version")
    parser.add_argument('--sckan-version', dest='sckan_version', metavar='SCKAN_VERSION', help='SCKAN version to check, e.g. sckan-2024-03-26', required=True)
    parser.add_argument('--output-dir', dest='output_dir', metavar='OUTPUT_DIR', help='Directory to store the extracted knowledge', required=True)

    try:
        args = parser.parse_args()
        extracting_knowledge(args)
    except PathError as error:
        sys.stderr.write(f'{error}\n')
        sys.exit(1)
    sys.exit(0)

#===============================================================================

if __name__ == '__main__':
    main()

#===============================================================================