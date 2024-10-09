#===============================================================================
#
#  Flatmap viewer and annotation tools
#
#  Copyright (c) 2019-21  David Brooks
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#===============================================================================

import os
import logging
import tempfile
from typing import Any, Optional
import networkx as nx

#===============================================================================

# Create a temporary directory for neurondm to look in to see if NPO is already
# checked out. This prevents neurondm from trying to use some other git repository
# above the installation directory of its Python package

temp_directory = tempfile.TemporaryDirectory()
os.environ['PYONTUTILS_ONTOLOGY_LOCAL_REPO'] = temp_directory.name

# Suppress logging of all messages while neurondm and pyontutils are imported
logging.disable(logging.CRITICAL+1)

from neurondm.core import Config, graphBase, NegPhenotype
from neurondm.core import OntTerm, OntId, RDFL
from neurondm import orders

from pyontutils.core import OntGraph, OntResIri
from pyontutils.namespaces import rdfs, ilxtr

# Renable general logging
logging.disable(logging.NOTSET)

# Suppress all messages from neurondm
logger = logging.getLogger('neurondm')
logger.setLevel(logging.CRITICAL+1)

#===============================================================================

import rdflib

#===============================================================================

from .apinatomy import EXCLUDED_LAYERS
from .namespaces import NAMESPACES
from .utils import request_json, log

#===============================================================================

NPO_OWNER = 'SciCrunch'
NPO_REPO = 'NIF-Ontology'
NPO_API = f'https://api.github.com/repos/{NPO_OWNER}/{NPO_REPO}'
NPO_RAW = f'https://raw.githubusercontent.com/{NPO_OWNER}/{NPO_REPO}'
NPO_GIT = f'https://github.com/{NPO_OWNER}/{NPO_REPO}'

NPO_TTLS = ('apinat-partial-orders',
            'apinat-pops-more',
            'apinat-simple-sheet',
            'sparc-nlp')

GEN_NEURONS_PATH = 'ttl/generated/neurons/'
TURTLE_SUFFIX = '.ttl'

#===============================================================================

class NPOException(Exception):
    pass

#===============================================================================

#### Functions to load knowledge from SCKAN Github ###

def makelpesrdf() -> tuple:
#==========================
    collect = []
    def lpes(neuron, predicate):
        """ get predicates from python bags """
        # TODO could add expected cardinality here if needed
        return [NAMESPACES.curie(str(o)) for o in neuron.getObjects(predicate)
                if not collect.append((predicate, o))]

    def lrdf(neuron, predicate):
        """ get predicates from graph """
        return [  # XXX FIXME core_graph bad etc.
            NAMESPACES.curie(str(o)) for o in
            neuron.core_graph[neuron.identifier:predicate]]

    return lpes, lrdf, collect

def simplify(e: Any) -> Any:
#===========================
    if e is None:
        return
    elif isinstance(e, rdflib.Literal):  # blank case
        return e.toPython()
    else:
        return OntTerm(e).curie

def simplify_nested(f, nested):
#==============================
    for e in nested:
        if isinstance(e, list) or isinstance(e, tuple):
            yield tuple(simplify_nested(f, e))
        elif isinstance(e, orders.rl):
            yield orders.rl(f(e.region), f(e.layer))
        else:
            yield f(e)

def for_composer(n, cull=False) -> dict[str, Any]:
#=================================================
    lpes, lrdf, collect = makelpesrdf()
    _po = n.partialOrder()
    fc = dict(
        id = NAMESPACES.curie(str(n.id_)),
        label = str(n.origLabel),
        origin = [l for l in lpes(n, ilxtr.hasSomaLocatedIn)],
        dest = (
            # XXX looking at this there seems to be a fault assumption that
            # there is only a single destination type per statement, this is
            # not the case, there is destination type per destination
            [dict(loc=l, type='AXON-T') for l in lpes(n, ilxtr.hasAxonPresynapticElementIn)] +
            # XXX I strongly reccoment renaming this to SENSORY-T so that the
            # short forms are harder to confuse A-T and S-T
            [dict(loc=l, type='AFFERENT-T') for l in lpes(n, ilxtr.hasAxonSensorySubcellularElementIn)] +
            [dict(loc=l, type='AFFERENT-T') for l in lpes(n, ilxtr.hasAxonLeadingToSensorySubcellularElementIn)]
        ),
        order = tuple(simplify_nested(simplify, _po)) if _po else [],
        path = (  # TODO pull ordering from partial orders (not implemented in core atm)
            [dict(loc=l, type='AXON') for l in lpes(n, ilxtr.hasAxonLocatedIn)] +
            # XXX dendrites don't really ... via ... they are all both terminal and via at the same time ...
            [dict(loc=l, type='DENDRITE') for l in lpes(n, ilxtr.hasDendriteLocatedIn)]
        ),
        #laterality = lpes(n, ilxtr.hasLaterality),  # left/rigth tricky ?
        #projection_laterality = lpes(n, ilxtr.???),  # axon located in contra ?
        species =            [l for l in lpes(n, ilxtr.hasInstanceInTaxon)],
        sex =                [NAMESPACES.curie(str(p.p)) for p in n if not isinstance(p, NegPhenotype) and p.e==ilxtr.hasBiologicalSex and not collect.append((ilxtr.hasBiologicalSex , p.p))],
        neg_sex =            [NAMESPACES.curie(str(p.p)) for p in n if isinstance(p, NegPhenotype) and p.e==ilxtr.hasBiologicalSex and not collect.append((ilxtr.hasBiologicalSex , p.p))],
        circuit_type =       lpes(n, ilxtr.hasCircuitRolePhenotype),
        phenotype =          [l for l in lpes(n, ilxtr.hasAnatomicalSystemPhenotype)],  # current meaning of composer phenotype
        anatomical_system =  [l for l in lpes(n, ilxtr.hasAnatomicalSystemPhenotype)],
        # there are a number of dimensions that we aren't converting right now
        dont_know_fcrp =     lpes(n, ilxtr.hasFunctionalCircuitRolePhenotype),
        other_phenotype = (  lpes(n, ilxtr.hasPhenotype)
                           + lpes(n, ilxtr.hasMolecularPhenotype)
                           + lpes(n, ilxtr.hasProjectionPhenotype)),
        forward_connection = lpes(n, ilxtr.hasForwardConnectionPhenotype),

        # direct references from individual individual neurons
        provenance =      lrdf(n, ilxtr.literatureCitation),
        sentence_number = lrdf(n, ilxtr.sentenceNumber),
        note_alert =      lrdf(n, ilxtr.alertNote),
        # XXX provenance from ApiNATOMY models as a whole is not ingested
        # right now because composer lacks support for 1:n from neuron to
        # prov, (or rather lacks prov collections) and because it attaches
        # prov to the sentece, which does not exist for all neurons

        # TODO more ...
        # notes = ?

        # for _ignore, hasClassificationPhenotype is used for ApiNATOMY
        # unlikely to be encountered for real neurons any time soon
        _ignore = [l for l in lpes(n, ilxtr.hasClassificationPhenotype)],  # used to ensure we account for all phenotypes
    )
    npo = set((p.e, p.p) for p in n.pes)
    cpo = set(collect)
    unaccounted_pos = npo - cpo
    if unaccounted_pos:
        log.warning(
            str([n.id_, [[n.in_graph.namespace_manager.qname(e) for e in pos]
                     for pos in unaccounted_pos]]))
    return {k:v for k, v in fc.items() if v} if cull else fc

def get_connectivity_edges(partial_order) -> list:
#=================================================
    # functions to parse connectivities
    def parse_connectivities(connectivities, partial_order):#, root: str|tuple="blank"):
        if len(partial_order) > 1:
            root = (
                        (
                            partial_order[0].layer, 
                            tuple([partial_order[0].region]),
                        ) 
                        if isinstance(partial_order[0], orders.rl)
                        else (partial_order[0], ())
                    )
            for sub_partial_order in partial_order[1:]:
                adj = (
                    (
                        sub_partial_order[0].layer, 
                        tuple([sub_partial_order[0].region]),
                    ) 
                    if isinstance(sub_partial_order[0], orders.rl)
                    else (sub_partial_order[0], ())
                )
                connectivities += [(root, adj)]
                if len(sub_partial_order) > 1:
                    parse_connectivities(connectivities, sub_partial_order)
    connectivities = []
    if partial_order != "blank":
        parse_connectivities(connectivities, partial_order)

    # filter layer terms, returning filtered_edge
    filtered_connectivities = []
    for edge in connectivities:
        new_edge = []
        for node in edge:
            new_node = []
            for terms in node:
                if isinstance(terms, tuple):
                    terms = [t for t in terms if t not in EXCLUDED_LAYERS]
                    new_node += [tuple(terms)]
                else:
                    terms = terms if terms not in EXCLUDED_LAYERS else []
                    new_node += [terms]
            if isinstance((node_0:=new_node[0]), orders.rl):
                node_0 = [node_0.region, (node_0.layer,)]
            else:
                node_0 = [node_0, ()]
            if len(new_node[0]) == 0 and len(new_node[1]) == 0:
                continue
            elif len(new_node[0]) == 0:
                new_node = [new_node[1][0], tuple(list(new_node[1])[1:])]
            new_edge += [tuple(new_node)]
        if ("blank", ()) in new_edge or len(new_edge) < 2:
            continue
        if new_edge[0] == new_edge[1]:
            continue
        filtered_connectivities += [tuple(new_edge)]
    return list(set(filtered_connectivities))

def load_knowledge_from_ttl(npo_release: str) -> tuple:
#======================================================
    g = OntGraph()  # load and query graph
    neuron_knowledge = {}
    neuron_terms = {}

    # remove scigraph and interlex calls
    graphBase._sgv = None
    del graphBase._sgv
    if len(OntTerm.query._services) > 1:
        # backup services and avoid issues on rerun
        _old_query_services = OntTerm.query._services
        _noloc_query_services = _old_query_services[1:]

    OntTerm.query._services = (RDFL(g, OntId),)

    for f in NPO_TTLS:
        ori = OntResIri(f'{NPO_RAW}/{npo_release}/{GEN_NEURONS_PATH}{f}{TURTLE_SUFFIX}')
        [g.add(t) for t in ori.graph]

    for f in ('apinatomy-neuron-populations', '../../npo'):
        p = os.path.normpath(GEN_NEURONS_PATH + f)
        ori = OntResIri(f'{NPO_RAW}/{npo_release}/{p}{TURTLE_SUFFIX}')
        [g.add((s, rdfs.label, o)) for s, o in ori.graph[:rdfs.label:]]

    config = Config('npo-connectivity')
    config.load_existing(g)
    neurons = config.neurons()  # scigraph required here if deps not removed above

    for n in neurons:
        neuron = for_composer(n)
        neuron['connectivity'] = get_connectivity_edges(neuron['order'])
        neuron['class'] = f'ilxtr:{type(n).__name__}'
        neuron['terms-dict'] = {NAMESPACES.curie(str(p.p)):str(p.pLabel) for p in n}
        neuron['terms-dict'][neuron['id']] = neuron['label']
        if neuron['connectivity']:
            neuron['is-connected'] = nx.is_connected(nx.Graph(neuron['connectivity']))
        else:
            neuron['is-connected'] = False
        neuron_terms = {**neuron_terms, **neuron['terms-dict']}
        neuron_knowledge[neuron['id']] = neuron

    return neuron_knowledge, neuron_terms, g

#===============================================================================

class Npo:
    def __init__(self, npo_release: Optional[str]):
        self.__npo_release = self.__check_npo_release(npo_release)
        self.__npo_knowledge, self.__npo_terms, self.__rdf_graph = load_knowledge_from_ttl(self.__npo_release)

    @property
    def release(self) -> str:
    #========================
        return self.__npo_release

    def __check_npo_release(self, npo_release) -> str:
    #=================================================
        if (response:=request_json(f'{NPO_API}/releases')) is not None:
            releases = {r['tag_name']:r for r in response if r['tag_name'].startswith('sckan-')}
            if npo_release is None:
                if len(releases):
                    # Use most recent
                    npo_release = sorted(releases.keys())[-1]
                    log.warning(f'No NPO release given: used {npo_release}')
                else:
                    raise NPOException(f'No NPO releases available')
            elif npo_release not in releases:
                raise NPOException(f'Unknown NPO release: {npo_release}')

            release = releases[npo_release]
            response = request_json(f'{NPO_API}/git/refs/tags/{release["tag_name"]}')
            self.__npo_build = {
                'sha': response['object']['sha'] if response is not None else None,
                'released': release['created_at'].split('T')[0],
                'release': release["tag_name"],
                'path': f'{NPO_GIT}/tree/{release["tag_name"]}'
            }
            return release['tag_name']
        else:
            raise NPOException(f'NPO at {NPO_API} is not available')

    def connectivity_models(self) -> list[str]:
    #==========================================
        return list({v['class'] for v in self.__npo_knowledge.values()})
    
    def connectivity_paths(self, connected_only = True) -> list[str]:
    #=========================================
        if connected_only:
            return list(path for path, knowledge in self.__npo_knowledge.items() if knowledge['is-connected'])
        else:
            return list(path for path in self.__npo_knowledge.keys())

    def build(self) -> dict[str, str]:
    #=================================
        return self.__npo_build
    
    def get_knowledge(self, entity) -> dict[str, Any]:
    #=================================================
        knowledge = {
            'id': entity
        }
        # get label from npo_terms or from rdflib's graph
        if entity in self.__npo_terms:
            knowledge['label'] = self.__npo_terms[entity]
        else:
            if len(labels:=[o for o in self.__rdf_graph.objects(subject=NAMESPACES.uri(entity), predicate=rdfs.label)]) > 0:
                knowledge['label'] = labels[0]

        # check if entity is a connectivity model
        if entity in self.connectivity_models():
            if 'label' not in knowledge: knowledge['label'] = entity
            knowledge['paths'] = [{'id': v['id'], 'models': v['id']} for v in self.__npo_knowledge.values() if v['class'] == entity]
            knowledge['references'] = []

        # check if entity is a connecitvity path
        if (path_kn:=self.__npo_knowledge.get(entity)) is not None:
            if 'label' not in knowledge: knowledge['label'] = path_kn['label']
            knowledge['long-label'] = path_kn['label']
            knowledge['connectivity'] = path_kn['connectivity']
            if len(phenotype:=path_kn['phenotype']+path_kn['circuit_type']) > 0:
                knowledge['phenotypes'] = phenotype
            if len(taxon:=path_kn['species']) > 0:
                knowledge['taxons'] = taxon
            else:
                knowledge['taxons'] = ['NCBITaxon:40674']      # Default to Mammalia
            if len(sex:=path_kn['sex']) == 1:
                knowledge['biologicalSex'] = sex[0]
            if len(alert:=path_kn['note_alert']) > 0:
                knowledge['alert'] = alert
            nodes = {}
            for c in path_kn['connectivity']:
                nodes[tuple([c[0][0]] + list(c[0][1]))] = c[0]
                nodes[tuple([c[1][0]] + list(c[1][1]))] = c[1]
            c_dendrites = {d:[c for c in nodes if d in c] for d in path_kn['origin']}
            dendrites = [nodes[c] for cd_list in c_dendrites.values() for c in cd_list if len(c) == len(max(cd_list, key=len))]
            knowledge['dendrites'] = list(set(dendrites))
            c_axons = {a['loc']:[c for c in nodes if a['loc'] in c] for a in path_kn['dest']}
            axons = [nodes[c] for cd_list in c_axons.values() for c in cd_list if len(c) == len(max(cd_list, key=len))]
            knowledge['axons'] = list(set(axons))
            if len(references:=path_kn['provenance']) > 0:
                knowledge['references'] = references
            knowledge['is-connected'] = path_kn.get('is-connected', False)

        return knowledge

    def extracted_knowledge(self):
    #==========================================
        source = f'{self.__npo_release}-npo'
        npo_knowledge = {
            'source': source,
            'knowledge': []
        }
        for term in self.__npo_terms:
            term_knowledge = self.get_knowledge(term)
            term_knowledge['source'] = f'{self.__npo_release}-npo'
            npo_knowledge['knowledge'].append(term_knowledge)

        return npo_knowledge
#===============================================================================
