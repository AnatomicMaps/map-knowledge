#===============================================================================

from collections import defaultdict

#===============================================================================

from mapknowledge import KnowledgeStore
import networkx as nx

#===============================================================================

def sckan_stats(sckan_version):
    store = KnowledgeStore(sckan_version=sckan_version)

    paths = set()
    edges = set()
    nodes = set()
    terms = set()
    phenotypes = defaultdict(set)
    disconnected_paths = []
    missing_forwardings = []
    no_connectivity_paths = []

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
            G = nx.Graph()
            G.add_edges_from(conn)
            if not nx.is_connected(G):
                disconnected_paths.append(path_id)
            for fc in np.get('forward-connections', []):
                if fc not in store.connectivity_paths():
                    missing_forwardings.append((path_id, fc))
        else:
            no_connectivity_paths.append(path_id)
            print(f'Warning: No connectivity for path {path_id}')

    result = {
        'neuron-populations': len(paths),
        'edges': len(edges),
        'nodes': len(nodes),
        'terms': len(terms),
        'phenotypes': {
            phenotype: len(pnodes)
            for phenotype, pnodes in phenotypes.items()
        },
        'disconnected-paths': disconnected_paths,
        'missing-forwardings': missing_forwardings,
        'no-connectivity-paths': no_connectivity_paths,
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
    parser.add_argument('-d', '--debug', action='store_true', help='Show DEBUG log messages')
    args = parser.parse_args()

    stats = sckan_stats(args.sckan_version)

    print(f'- The number of neuron populations having connectivity: {stats["neuron-populations"]}')
    print(f'- The number of unique edges: {stats["edges"]}')
    print(f'- The number of unique nodes: {stats["nodes"]}')
    print(f'- The number of unique terms: {stats["terms"]}')
    for phenotype, pnum in stats['phenotypes'].items():
        print(f'- The number of unique {phenotype}: {pnum}')
    print(f'- The number of disconnected paths: {len(stats["disconnected-paths"])}')
    print(f'- The number of missing forward connections: {len({t[1] for t in stats["missing-forwardings"]})}')
    print(f'- The number of paths with no connectivity: {len(stats["no-connectivity-paths"])}')

    if args.debug:
        if len(stats["disconnected-paths"]) > 0:
            print('\nDisconnected paths:')
            for dp in stats["disconnected-paths"]:
                print(f'  - {dp}')
        if len(stats["missing-forwardings"]) > 0:
            print('\nMissing forward connections:')
            for mp in stats["missing-forwardings"]:
                print(f'  - From {mp[0]} to missing {mp[1]}')
        if len(stats["no-connectivity-paths"]) > 0:
            print('\nPaths with no connectivity:')
            for np in stats["no-connectivity-paths"]:
                print(f'  - {np}')
#===============================================================================

if __name__ == '__main__':
#=========================
    main()

#===============================================================================
