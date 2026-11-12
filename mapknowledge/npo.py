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
import urllib.parse
from collections import defaultdict
import itertools

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
from neurondm.core import IntersectionOf

from pyontutils.core import OntGraph, OntResIri
from pyontutils.namespaces import rdfs, ilxtr, skos

# Renable general logging
logging.disable(logging.NOTSET)

# Suppress all messages from neurondm
logger = logging.getLogger('neurondm')
logger.setLevel(logging.CRITICAL+1)

#===============================================================================

import rdflib

#===============================================================================

from .anatomical_types import NERVE_TYPE
from .apinatomy import EXCLUDED_LAYERS
from .namespaces import NAMESPACES
from .utils import request_json, log

#===============================================================================

NPO_OWNER = 'SciCrunch'
NPO_REPO = 'NIF-Ontology'
NPO_API = f'https://api.github.com/repos/{NPO_OWNER}/{NPO_REPO}'
NPO_RAW = f'https://raw.githubusercontent.com/{NPO_OWNER}/{NPO_REPO}'
NPO_GIT = f'https://github.com/{NPO_OWNER}/{NPO_REPO}'

NPO_APINATOMY_TTLS = [
    'apinat-complex',
    'apinat-manual',
]

NPO_APINATOMY_LEGACY_TTLS = [
    'apinat-partial-orders',
    'apinat-pops-more',
    'apinat-simple-sheet',
    'apinatomy-neuron-populations',
    '../../npo-annotations',
]

NPO_NLP_TTLS = [
    'composer-nlp',
]

NPO_NLP_LEGACY_TTLS = [
    'sparc-nlp',
]

NPO_COMPOSER_TTLS = [
    'composer',
]

LABEL_TTLS = [
    '../../npo',
    '../../sparc-community-terms',
    '../../phenotypes',
    '../../phenotype-indicators'
]

PRECISION_TTLS = [
    'precision'
]

GEN_NEURONS_PATH = 'ttl/generated/neurons/'
TURTLE_SUFFIX = '.ttl'

#===============================================================================

NODE_PHENOTYPES = [
    ilxtr.hasSomaLocatedIn,
    ilxtr.hasAxonPresynapticElementIn,
    ilxtr.hasAxonSensorySubcellularElementIn,
    ilxtr.hasAxonLeadingToSensorySubcellularElementIn,
    ilxtr.hasAxonLocatedIn,
    ilxtr.hasDendriteLocatedIn,
]

DESCRIPTIVE_PHENOTYPES = [
    ilxtr.hasPhenotype,
    ilxtr.hasMolecularPhenotype,
    ilxtr.hasProjectionPhenotype,
    ilxtr.hasFunctionalCircuitRolePhenotype,
    ilxtr.hasThresholdPhenotype,
    ilxtr.hasNeurotransmitterPhenotype,
    ilxtr.hasFunctionalPhenotype,
    ilxtr.hasAxonPhenotype,
    ilxtr.hasSomaPhenotype,
    ilxtr.hasAxonSensorySubcellularStructure,
    ilxtr.hasExpressionPhenotype,
    ilxtr.hasNucleicAcidExpressionPhenotype,
    ilxtr.hasDriverExpressionPhenotype,
    ilxtr.hasDriverExpressionConstitutivePhenotype,
    ilxtr.hasDriverExpressionInducedPhenotype,
    ilxtr.hasReporterExpressionPhenotype,
    ilxtr.hasProteinExpressionPhenotype,
    ilxtr.hasAdaptationPhenotype,
    ilxtr.isMemberOfCircuit,
]

EXPRESSION_LEVELS = [
    ilxtr.HigherExpression,
    ilxtr.LowerExpression,
]

#===============================================================================

ANATOMICAL_TYPES = {
    NERVE_TYPE: [
        'UBERON:0001021',                       # Nerve
        'FMA:5860',                             # Spinal nerve
        'FMA:65132',                            # Nerve
    ]
}

ANATOMICAL_TYPES_QUERY = """
    SELECT ?term ?label WHERE {
        values ?termClasses { %TYPE_CLASSES% }
        ?term rdfs:subClassOf* ?termClasses .
        optional { ?term rdfs:label ?label }
    }
"""

#===============================================================================

NPO_TERM_LABELS = f"""
    SELECT ?term ?label WHERE {{
        ?term rdfs:label ?label
        filter(strStarts(str(?term), "{NAMESPACES.namespaces['UBERON']}")
            || strStarts(str(?term), "{NAMESPACES.namespaces['ILX']}"))
    }}
"""

#===============================================================================

EXCLUDED_PREFIXES = [
    'http://uri.interlex.org/tgbugs/uris/readable/apinat-simple/'
]

#===============================================================================

type KnowledgeDict = dict[str, Any]

#===============================================================================

class NPOException(Exception):
    pass

#===============================================================================

#### Functions to load knowledge from SCKAN Github ###
## https://github.com/tgbugs/pyontutils/blob/master/neurondm/docs/composer.py

def makelpesrdf() -> tuple:
#==========================
    collect = []
    def lpes(neuron, predicate):
        """ get predicates from python bags """
        # TODO could add expected cardinality here if needed
        results = []
        def _add(obj):
            result = tuple(NAMESPACES.curie(str(m)) for m in obj.members()) if isinstance(obj, IntersectionOf) else tuple([NAMESPACES.curie(str(obj))])
            if result not in results:
                results.append(result)
                collect.append((predicate, obj))

        for obj in neuron.getObjects(predicate):
            _add(obj)
        predicate_curie = NAMESPACES.curie(str(predicate))
        for p in neuron.pes:
            if hasattr(p, 'pes'):
                for p2 in p.pes:
                    if NAMESPACES.curie(str(p2.e)) == predicate_curie:
                        _add(p2.p)
        return results

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
        long_label = str(pref_labels[0]) if (pref_labels:=lrdf(n, skos.prefLabel)) else str(n.origLabel),
        # Connectivity ---
        origin = lpes(n, ilxtr.hasSomaLocatedIn),
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
        #laterality = lpes(n, ilxtr.hasLaterality),  # left/right tricky ?
        projection_lateralities = [l[0] for l in lpes(n, ilxtr.hasProjectionLaterality)],
        forward_connections = [fc[0] for fc in lpes(n, ilxtr.hasForwardConnectionPhenotype)],
        # Common metadata ---
        species =            [l[0] for l in lpes(n, ilxtr.hasInstanceInTaxon)],
        sex =                [NAMESPACES.curie(str(p.p)) for p in n if not isinstance(p, NegPhenotype) and p.e==ilxtr.hasBiologicalSex and not collect.append((ilxtr.hasBiologicalSex , p.p))],
        neg_sex =            [NAMESPACES.curie(str(p.p)) for p in n if isinstance(p, NegPhenotype) and p.e==ilxtr.hasBiologicalSex and not collect.append((ilxtr.hasBiologicalSex , p.p))],
        circuit_type =       [l[0] for l in lpes(n, ilxtr.hasCircuitRolePhenotype)],
        phenotype =          [l[0] for l in lpes(n, ilxtr.hasAnatomicalSystemPhenotype)],  # current meaning of composer phenotype
        anatomical_system =  [l[0] for l in lpes(n, ilxtr.hasAnatomicalSystemPhenotype)],
        # there are a number of dimensions that we aren't converting right now
        descriptive_phenotypes = {NAMESPACES.curie(str(pn)): lpes(n, pn) for pn in DESCRIPTIVE_PHENOTYPES},
        node_phenotypes =    {NAMESPACES.curie(str(pn)): lpes(n, pn) for pn in NODE_PHENOTYPES},

        # Subclass relationships (e.g. EMP:subClassOf npokb:915)
        subclass_of =        lrdf(n, rdflib.URIRef('http://uri.interlex.org/temp/uris/subClassOf')),
        # Corresponding cell types in other papers (directed, many-to-many, may cross species)
        maps_to =            lrdf(n, rdflib.URIRef('http://uri.interlex.org/temp/uris/mapsTo')),

        # Provenance ---
        provenance =      lrdf(n, ilxtr.literatureCitation),
        sentence_number = lrdf(n, ilxtr.sentenceNumber),
        note_alert =      lrdf(n, ilxtr.alertNote),
        expert_consultants = lrdf(n, ilxtr.expertConsultant),
        curator_note =       lrdf(n, ilxtr.curatorNote),
        data_citation =      lrdf(n, ilxtr.dataCitation),
        # XXX provenance from ApiNATOMY models as a whole is not ingested
        # right now because composer lacks support for 1:n from neuron to
        # prov, (or rather lacks prov collections) and because it attaches
        # prov to the sentece, which does not exist for all neurons

        # TODO more ...
        # notes = ?

        # for _ignore, hasClassificationPhenotype is used for ApiNATOMY
        # unlikely to be encountered for real neurons any time soon
        _ignore = [l[0] for l in lpes(n, ilxtr.hasClassificationPhenotype)],  # used to ensure we account for all phenotypes
    )
    npo = set(
        item for p in n.pes
        for item in (
            ((p2.e, p2.p) for p2 in p.pes) if hasattr(p, 'pes')
            else ((p.e, p.p),)
        )
    )
    cpo = set(collect)
    unaccounted_pos = npo - cpo
    if unaccounted_pos:
        log.warning(
            str([n.id_, [[tuple(m for m in e) if type(e)==tuple or type(e)==frozenset else e for e in pos]
                     for pos in unaccounted_pos]]))
    return {k:v for k, v in fc.items() if v} if cull else fc

#### End of extract from https://github.com/tgbugs/pyontutils/blob/master/neurondm/docs/composer.py

#===============================================================================

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

#===============================================================================

class Npo:
    def __init__(self, npo_release: Optional[str]):
        self.__npo_release = self.__check_npo_release(npo_release)
        self.__rdf_graph = OntGraph()
        self.__composer_neurons = {}
        self.__composer_cells = {}
        self.__neuron_knowledge = {}
        self.__npo_terms: dict[rdflib.URIRef, KnowledgeDict] = {}

        self.__load_knowledge_from_ttl()
        self.__load_anatomical_types()
        self.__load_npo_terms()
        for neuron_id in self.__composer_neurons.keys():
            self.__get_term_knowledge(neuron_id)
            self.__get_neuron_knowledge(neuron_id)
        for cell_id in self.__composer_cells.keys():
            self.__get_term_knowledge(cell_id)

    @property
    def connectivity_models(self) -> list[str]:
    #==========================================
        return list({v.get('class') for v in self.__composer_neurons.values()})

    @property
    def connectivity_paths(self) -> list[str]:
    #=========================================
        return list(self.__composer_neurons.keys())

    @property
    def cell_models(self) -> list[str]:
    #==========================================
        return list({v.get('class') for v in self.__composer_cells.values()})

    @property
    def cell_precisions(self) -> list[str]:
    #=================================
        # return list({id for id, v in self.__composer_cells.items() if len(v.get('subclass_of', []))>0})
        # will be updated when available
        return list(self.__composer_cells.keys())

    @property
    def release(self) -> str:
    #========================
        return self.__npo_release

    @property
    def terms(self) -> list[str]:
    #============================
        return [NAMESPACES.curie(term) for term in self.__npo_terms.keys()]

    def build(self) -> dict[str, str]:
    #=================================
        return self.__npo_build

    def terms_of_type(self, anatomical_type: str) -> list[str]:
    #==========================================================
        return [NAMESPACES.curie(term)
                    for term in self.__anatomical_terms_by_type.get(anatomical_type, [])]

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

    def __load_knowledge_from_ttl(self):
    #===================================
        ## Following is based on github.com/tgbugs/pyontutils/blob/master/neurondm/neurondm/models/composer.py

        # remove scigraph and interlex calls
        graphBase._sgv = None       # type: ignore
        del graphBase._sgv

        def load_path_knowledge_ttls(ttls):
            g = OntGraph()
            for f in ttls:
                ori = OntResIri(f'{NPO_RAW}/{self.__npo_release}/{GEN_NEURONS_PATH}{f}{TURTLE_SUFFIX}')
                try:
                    if ori.graph is not None:
                        if f == 'apinat-manual':
                            for s, p, o in ori.graph:
                                if not (
                                    p == rdfs.subClassOf
                                    and (o, rdfs.subClassOf, ilxtr.NeuronApinatComplex) in ori.graph
                                ):
                                    g.add((s, p, o))
                        elif f == 'apinatomy-neuron-populations':
                            [self.__rdf_graph.add((s, rdfs.label, o))
                                for s, o in ori.graph.subject_objects(rdfs.label)]
                        else:
                            [g.add(t) for t in ori.graph]
                except:
                    log.warning(f'Could not fetch {ori.iri} from {self.__npo_release}.')
                    return None
            return g

        OntTerm.query._services = (RDFL(self.__rdf_graph, OntId),)
        # Load ApiNATOMY
        if (apinatomy_graph := load_path_knowledge_ttls(NPO_APINATOMY_TTLS)) is None:
            apinatomy_graph = load_path_knowledge_ttls(NPO_APINATOMY_LEGACY_TTLS)
        self.__rdf_graph += apinatomy_graph if apinatomy_graph is not None else OntGraph()
        # Load SPARC_NLP
        if (nlp_graph := load_path_knowledge_ttls(NPO_NLP_TTLS)) is None:
            nlp_graph = load_path_knowledge_ttls(NPO_NLP_LEGACY_TTLS)
        self.__rdf_graph += nlp_graph if nlp_graph is not None else OntGraph()
        # Load pain, portal, and gastInt
        if (composer_graph := load_path_knowledge_ttls(NPO_COMPOSER_TTLS)) is not None:
            self.__rdf_graph += composer_graph

        for f in LABEL_TTLS:
            p = urllib.parse.quote(GEN_NEURONS_PATH + f)
            ori = OntResIri(f'{NPO_RAW}/{self.__npo_release}/{p}{TURTLE_SUFFIX}')
            if ori.graph is not None:
                [self.__rdf_graph.add((s, rdfs.label, o))
                    for s, o in ori.graph.subject_objects(rdfs.label)]
                [self.__rdf_graph.add((s, rdfs.subClassOf, o))
                    for s, o in ori.graph.subject_objects(rdfs.subClassOf)]
                [self.__rdf_graph.add((s, ilxtr.hasExistingId, o))
                    for s, o in ori.graph.subject_objects(ilxtr.hasExistingId)]

        # Load types
        type_graph = load_path_knowledge_ttls(PRECISION_TTLS)
        self.__rdf_graph += type_graph if type_graph is not None else OntGraph()

        config = Config('npo-connectivity')
        config.load_existing(self.__rdf_graph)

        for neuron in config.neurons():
            if not any(neuron.id_.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
                kn = for_composer(neuron)
                kn['class'] = type(neuron).__name__
                if type(neuron).__name__ == 'NeuronPrecision':
                    self.__composer_cells[kn['id']] = kn
                else:
                    self.__composer_neurons[kn['id']] = kn

    def __load_anatomical_types(self):
    #=================================
        self.__anatomical_terms_by_type = defaultdict(list)
        self.__anatomical_types_by_label = defaultdict(list)
        self.__anatomical_types_by_term = defaultdict(list)
        for anatomical_type, classes in ANATOMICAL_TYPES.items():
            for row in self.__rdf_graph.query(ANATOMICAL_TYPES_QUERY.replace('%TYPE_CLASSES%',
                                                                             ' '.join(classes)),
                                              initNs=NAMESPACES.namespaces):
                term: rdflib.URIRef = row[0]                                    # type: ignore
                self.__anatomical_terms_by_type[anatomical_type].append(term)
                self.__anatomical_types_by_term[term].append(anatomical_type)
                if (label := row[1]) is not None:                               # type: ignore
                    self.__anatomical_types_by_label[str(label).lower()].append(anatomical_type)

    def __load_npo_terms(self):
    #==========================
        self.__npo_terms: dict[rdflib.URIRef, KnowledgeDict] = {}
        for row in self.__rdf_graph.query(NPO_TERM_LABELS, initNs=NAMESPACES.namespaces):
            term: rdflib.URIRef = row[0]                                        # type: ignore
            label = str(row[1])                                                 # type: ignore
            if len(anatomical_types := self.__anatomical_types_by_term.get(term, [])):
                self.__npo_terms[term] = { 'label': label, 'type': anatomical_types[0] }
            elif len(anatomical_types := self.__anatomical_types_by_label.get(label.lower(), [])):
                self.__npo_terms[term] = { 'label': label, 'type': anatomical_types[0] }
                self.__anatomical_types_by_term[term] = anatomical_types
                for anatomical_type in anatomical_types:
                    self.__anatomical_terms_by_type[anatomical_type].append(term)
            else:
                self.__npo_terms[term] = { 'label': label }

    def __get_neuron_knowledge(self, id: str):
    #=========================================
        if (neuron := self.__neuron_knowledge.get(id)) is None:
            if (neuron := self.__composer_neurons.get(id)) is not None:
                neuron['connectivity'] = get_connectivity_edges(neuron['order'])
                neuron['terms-dict'] = {}
                # This makes sure we have knowledge for each term of connectivity nodes
                for conn in neuron['connectivity']:
                    for term in [conn[0][0], *conn[0][1], conn[1][0], *conn[1][1]]:
                        neuron_term = self.__get_term_knowledge(term)
                        if len(neuron_term):
                            neuron['terms-dict'][term] = neuron_term
                neuron['terms-dict'][neuron['id']] = {'label': neuron['label']}
                if neuron['connectivity']:
                    neuron['connected'] = nx.is_connected(nx.Graph(neuron['connectivity']))
                else:
                    neuron['connected'] = False
                self.__neuron_knowledge[id] = neuron
        return neuron

    def __get_term_knowledge(self, term: str|rdflib.URIRef) -> KnowledgeDict:
    #========================================================================
        if not isinstance(term, rdflib.URIRef):
            term = rdflib.URIRef(NAMESPACES.uri(term))
        npo_term = self.__npo_terms.get(term)
        if npo_term is None:
            npo_term = self.__term_knowledge(term)
            if npo_term is not None:
                self.__npo_terms[term] = npo_term
        return npo_term if npo_term is not None else {}

    def __term_knowledge(self, term: rdflib.URIRef) -> Optional[KnowledgeDict]:
    #==========================================================================
        if not (labels:=list(self.__rdf_graph.objects(term, rdfs.label))):
            for x in self.__rdf_graph.subjects(ilxtr.hasExistingId, term):
                if (labels:=list(self.__rdf_graph.objects(subject=x, predicate=rdfs.label))):
                    term = x         # type: ignore
                    break
        if labels:
            if len(anatomical_types := self.__anatomical_types_by_term.get(term, [])):
                return { 'label': str(labels[0]), 'type': anatomical_types[0] }
            else:
                return { 'label': str(labels[0]) }

    def get_knowledge(self, entity: str) -> KnowledgeDict:
    #=====================================================
        knowledge: KnowledgeDict = {
            'id': entity
        }
        knowledge.update(self.__get_term_knowledge(entity))

        # check if entity is a connectivity model or cell precision model
        models = None
        if entity in self.connectivity_models:
            models = self.__composer_neurons
        elif entity in self.cell_models:
            models = self.__composer_cells
        if models is not None:
            entry_key = 'paths' if models is self.__composer_neurons else 'cells'
            if 'label' not in knowledge: knowledge['label'] = entity
            knowledge[entry_key] = [{'id': v['id'], 'models': v['id']}
                                    for v in models.values() if v['class'] == entity]
            knowledge['references'] = [
                r for v in models.values() if v['class'] == entity
                for r in v['provenance']
            ]

        # shared common attributes
        def _add_common(kn: dict) -> None:
            if 'label' not in knowledge:
                knowledge['label'] = kn['label']
            knowledge['long-label'] = kn['long_label']
            if len(phenotype:=kn.get('phenotype', [])) > 0:
                knowledge['phenotypes'] = phenotype
            if len(taxon:=kn.get('species', [])) > 0:
                knowledge['taxons'] = taxon
            else:
                knowledge['taxons'] = ['NCBITaxon:40674']      # Default to Mammalia
            if len(sex:=kn.get('sex', [])) == 1:
                knowledge['biologicalSex'] = sex[0]
            if len(alert:=kn.get('note_alert', [])) > 0:
                knowledge['alert'] = alert
            if len(references:=kn.get('provenance', [])) > 0:
                knowledge['references'] = references
            if len(expert_consultants:=kn.get('expert_consultants', [])) > 0:
                knowledge['expert-consultants'] = expert_consultants
            if len(curator_note:=kn.get('curator_note', [])) > 0:
                knowledge['curator-note'] = curator_note
            if len(data_citation:=kn.get('data_citation', [])) > 0:
                knowledge['data-citations'] = data_citation
            if len(circuit:=kn.get('circuit_type', [])) > 0:
                knowledge['phenotypes'] = knowledge.get('phenotypes', []) + circuit
            knowledge['descriptive-phenotypes'] = {
                k: v
                for k, v in kn['descriptive_phenotypes'].items() if len(v) > 0
            }
            knowledge['class'] = kn['class']

        # connectivity neuron path
        def get_nodes(target_nodes, nodes):
            return list({
                tuple(node)
                for a in target_nodes
                if (n_id:=frozenset(a)) in nodes
                for node in nodes[n_id]
            })

        if (path_kn:=self.__get_neuron_knowledge(entity)) is not None:
            _add_common(path_kn)

            if len(projection_lateralities:=path_kn.get('projection_lateralities', [])) > 0:
                knowledge['projection-lateralities'] = projection_lateralities
            knowledge['connectivity'] = path_kn['connectivity']
            knowledge['pathDisconnected'] = not path_kn.get('connected', False)
            knowledge['forward-connections'] = path_kn['forward_connections']
            all_nodes = {n for edge in path_kn['connectivity'] for n in edge}
            node_coverage = defaultdict(list)       # (A, B) → [(A, (B)), (A, (B, C)), (A, (B, C, ...))]
            for node in all_nodes:
                n_id = [node[0], *node[1]]
                for r in range(1, len(n_id) + 1):
                    for comb in itertools.combinations(n_id, r):
                        node_coverage[frozenset(comb)].append(node)
            knowledge['dendrites'] = get_nodes([d['loc'] for d in path_kn['path']
                                                if d['type'] == 'DENDRITE'], node_coverage)
            knowledge['axons'] = get_nodes([a['loc'] for a in path_kn['path']
                                            if a['type'] == 'AXON'] +
                                            [a['loc'] for a in path_kn['dest']], node_coverage)
            knowledge['somas'] = get_nodes(path_kn['origin'], node_coverage)
            knowledge['axon-terminals'] = get_nodes([a['loc'] for a in path_kn['dest']
                                                     if a['type'] == 'AXON-T'], node_coverage)
            knowledge['afferent-terminals'] = get_nodes([a['loc'] for a in path_kn['dest']
                                                         if a['type'] == 'AFFERENT-T'], node_coverage)
            knowledge['axon-locations'] = get_nodes([a['loc'] for a in path_kn['path']
                                                     if a['type'] == 'AXON'], node_coverage)
            knowledge['node-phenotypes'] = {
                pn: get_nodes(locs, node_coverage)
                for pn, locs in path_kn['node_phenotypes'].items()
            }
            knowledge['nerves'] = [
                node
                for node in all_nodes
                if any(
                    self.__npo_terms.get(rdflib.URIRef(NAMESPACES.uri(t)), {}).get('type') == NERVE_TYPE
                    for t in [node[0], *node[1]]
                )
            ]

        # precision cell path
        elif (cell_kn:=self.__composer_cells.get(entity)) is not None:
            _add_common(cell_kn)

            knowledge['node-phenotypes'] = {
                pn: [(loc[0], tuple([*loc[1:]])) for loc in locs]
                for pn, locs in cell_kn['node_phenotypes'].items() if len(locs) > 0
            }
            knowledge['subclass-of'] = cell_kn.get('subclass_of', {})
            if len(maps_to:=[t for t in cell_kn.get('maps_to', []) if not t.startswith('TEMP:MISSING')]) > 0:
                knowledge['maps-to'] = maps_to

        return knowledge

#===============================================================================
