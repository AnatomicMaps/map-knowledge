#===============================================================================

from collections import defaultdict

#===============================================================================

from mapknowledge import KnowledgeStore

#===============================================================================

def sckan_stats(sckan_version):
    store = KnowledgeStore(sckan_version=sckan_version)

    paths = set()
    edges = set()
    nodes = set()
    terms = set()
    phenotypes = defaultdict(set)

    for path_id in store.connectivity_paths():
        np = store.entity_knowledge(path_id)
        if len(conn:=np.get('connectivity', [])) > 0:
            paths.add(path_id)
            for edge in conn:
                edges.add(edge)
                nodes.update(edge)
                terms.update([edge[0][0]] + list(edge[0][1]) + [edge[1][0]] + list(edge[1][1]))
            for phenotype, pnodes in np.get('node-phenotypes', {}).items():
                phenotypes[phenotype].update(pnodes)

    result = {
        'neuron-populations': len(paths),
        'edges': len(edges),
        'nodes': len(nodes),
        'terms': len(terms),
        'phenotypes': {
            phenotype: len(pnodes)
            for phenotype, pnodes in phenotypes.items()
        }
    }

    store.close()

    return result

#===============================================================================

def main():
    import logging
    logging.basicConfig(level=logging.INFO)

    import argparse
    parser = argparse.ArgumentParser(description='Get sckan_version stats.')
    parser.add_argument('-v', '--sckan-version', dest='sckan_version', default='sckan-2024-09-21')
    args = parser.parse_args()

    stats = sckan_stats(args.sckan_version)

    print(f'- The number of neuron populations having connectivity: {stats["neuron-populations"]}')
    print(f'- The number of unique edges: {stats["edges"]}')
    print(f'- The number of unique nodes: {stats["nodes"]}')
    print(f'- The number of unique terms: {stats["terms"]}')
    for phenotype, pnum in stats['phenotypes'].items():
        print(f'- The number of unique {phenotype}: {pnum}')

#===============================================================================

if __name__ == '__main__':
#=========================
    main()

#===============================================================================
