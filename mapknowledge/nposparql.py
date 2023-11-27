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

from pprint import pprint

from SPARQLWrapper import SPARQLWrapper2
from SPARQLWrapper.SmartWrapper import Value

import requests
import re
import ast

#===============================================================================

from .namespaces import NAMESPACES
from .apinatomy import EXCLUDED_LAYERS

#===============================================================================

NPO_NLP_NEURONS = 'ilxtr:sparc-nlp/'

#===============================================================================

NPO_SPARQL_ENDPOINT = 'https://blazegraph.scicrunch.io/blazegraph/sparql'

#===============================================================================

NPO_OWNER = "SciCrunch"
NPO_REPO = "NIF-Ontology"
NPO_BRANCH = "neurons"
NPO_SOURCE = f"https://raw.githubusercontent.com/{NPO_OWNER}/{NPO_REPO}/{NPO_BRANCH}/"
NPO_API = f"https://api.github.com/repos/{NPO_OWNER}/{NPO_REPO}/commits?sha={NPO_BRANCH}"
NPO_PATH = f"https://github.com/{NPO_OWNER}/{NPO_REPO}/blob/{NPO_BRANCH}/"
NPO_PARTIAL_ORDER = "ttl/generated/neurons/apinat-partial-orders.ttl"
NPO_PARTIAL_ORDER_URL = f"{NPO_SOURCE}{NPO_PARTIAL_ORDER}"
NPO_PARTIAL_ORDER_API = f"{NPO_API}&path={NPO_PARTIAL_ORDER}"
NPO_PARTIAL_ORDER_PATH = f"{NPO_PATH}{NPO_PARTIAL_ORDER}"

#===============================================================================

CONNECTIVITY = """
# Query to generate the adjacency matrix representing the axonal paths of the neuron populations.

PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ilxtr: <http://uri.interlex.org/tgbugs/uris/readable/>

SELECT DISTINCT ?Neuron_IRI ?V1 ?V2
WHERE
{{
    ?Neuron_IRI ilxtr:neuronPartialOrder ?PO .
        ?PO (rdf:rest|rdf:first)* ?r1 .
        ?r1 (rdf:rest|rdf:first)* ?r2 .
        ?r1 rdf:first ?V1 .
        ?r2 rdf:first ?V2 .
        ?V1 rdf:type owl:Class .
        ?V2 rdf:type owl:Class .

        FILTER (?mediator = ?r1)  # draw only from the same partial order
        ?mediator rdf:first ?V1 .  # car
        ?mediator rdf:rest+/rdf:first/rdf:first ?V2 .  # caadr

    FILTER (?V1 != ?V2).
    FILTER(?Neuron_IRI = {entity})
}}
ORDER BY ?V1 ?V2
LIMIT 10000
"""

#===============================================================================

"""
SELECT DISTINCT ?Neuron_IRI
{
   ?Neuron_IRI rdfs:subClassOf*/rdfs:label ?lbl. #http://uri.neuinfo.org/nif/nifstd/sao1417703748
   FILTER((?lbl = 'Neuron'))
}
ORDER BY ?Neuron_IRI
LIMIT 9999



"""

METADATA2 = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX partOf: <http://purl.obolibrary.org/obo/BFO_0000050>
    PREFIX ilxtr: <http://uri.interlex.org/tgbugs/uris/readable/>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT DISTINCT ?Neuron_IRI ?Neuron_Label ?Neuron_Pref_Label ?ObservedIn ?Sex
                    ?Phenotype ?Forward_Connections ?Alert ?Citation
    WHERE
    {{
        {{
            SELECT DISTINCT  ?Neuron_IRI ?Neuron_Label ?Neuron_Pref_Label ?Sex ?Alert ?Citation
            WHERE
            {{
                OPTIONAL{{?Neuron_IRI rdfs:label ?Neuron_Label.}}
                OPTIONAL{{?Neuron_IRI skos:prefLabel ?Neuron_Pref_Label.}}

                ?Neuron_IRI ilxtr:hasSomaLocation ?A_IRI.
                OPTIONAL {{?Neuron_IRI ilxtr:hasAxonLocation ?C_IRI.}}
                ?Neuron_IRI (ilxtr:hasAxonTerminalLocation | ilxtr:hasAxonSensoryLocation) ?B_IRI.

                OPTIONAL {{?Neuron_IRI ilxtr:hasPhenotypicSex ?Sex.}}
                OPTIONAL {{?Neuron_IRI ilxtr:literatureCitation ?Citation.}}
                OPTIONAL {{?Neuron_IRI ilxtr:alertNote ?Alert.}}
            }}
        }}

        {{
            SELECT DISTINCT  ?Neuron_IRI ?ObservedIn
            WHERE
            {{
                ?Neuron_IRI ilxtr:hasSomaLocation ?A_IRI.
                OPTIONAL {{?Neuron_IRI ilxtr:hasAxonLocation ?C_IRI.}}
                ?Neuron_IRI (ilxtr:hasAxonTerminalLocation | ilxtr:hasAxonSensoryLocation) ?B_IRI.

                OPTIONAL {{?Neuron_IRI ilxtr:isObservedInSpecies ?ObservedIn.}}
            }}
            GROUP BY ?Neuron_IRI ?ObservedIn
        }}
        {{
            SELECT DISTINCT  ?Neuron_IRI
            (group_concat(distinct ?ForwardConnection; separator=", ") as ?Forward_Connections)
            WHERE
            {{
                ?Neuron_IRI ilxtr:hasSomaLocation ?A_IRI.
                OPTIONAL {{?Neuron_IRI ilxtr:hasAxonLocation ?C_IRI.}}
                ?Neuron_IRI (ilxtr:hasAxonTerminalLocation | ilxtr:hasAxonSensoryLocation) ?B_IRI.

                OPTIONAL {{?Neuron_IRI ilxtr:hasForwardConnection ?ForwardConnection.}}
            }}
            GROUP BY ?Neuron_IRI
        }}

        {{
            SELECT DISTINCT  ?Neuron_IRI ?Phenotype
            WHERE
            {{
                ?Neuron_IRI ilxtr:hasSomaLocation ?A_IRI.
                OPTIONAL {{?Neuron_IRI ilxtr:hasAxonLocation ?C_IRI.}}
                ?Neuron_IRI (ilxtr:hasAxonTerminalLocation | ilxtr:hasAxonSensoryLocation) ?B_IRI.

                OPTIONAL {{?Neuron_IRI (ilxtr:hasNeuronalPhenotype |
                                      ilxtr:hasFunctionalCircuitRole |
                                      ilxtr:hasCircuitRole |
                                      ilxtr:hasProjection
                                      ) ?Phenotype.}}
            }}
            GROUP BY ?Neuron_IRI ?Phenotype
        }}
        FILTER(?Neuron_IRI = {entity})
    }}
    ORDER BY ?Neuron_IRI ?Neuron_Label
    LIMIT 10000
"""

"""
- Modify this query so it can handle neurons without soma and axon terminal in NPO
e.g. ilxtr:neuron-type-sstom-9.
- Filtering using ilxtr:NeuronApinatSimple || ilxtr:NeuronSparcNlp should be appropriate,
however, current NPO misses ilxtr:neuron-type-bolew-unbranched-25 rdfs:subClassOf ilxtr:NeuronSparcNlp,
therefore, teporarily using:
FILTER ((?type = ilxtr:NeuronEBM && REGEX(LCASE(STR(?Neuron_IRI)), 'type')) || (?type = ilxtr:NeuronSparcNlp))
- Using GROUP_BY and GROUP_CONCAT has_phenotype predicate used is not consistent, e.g.
each NLP neuron uses a single phenotype, such as ilxtr:neuron-phenotype-para-pre,
while an Apinatomy neurons may use use multiple phenotype, such as ilxtr:PreGanglionicPhenotype & ilxtr:ParasympatheticPhenotype

"""
METADATA = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX partOf: <http://purl.obolibrary.org/obo/BFO_0000050>
    PREFIX ilxtr: <http://uri.interlex.org/tgbugs/uris/readable/>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT DISTINCT ?Neuron_IRI ?Neuron_Label ?Neuron_Pref_Label ?ObservedIn ?Sex
                    (GROUP_CONCAT(DISTINCT ?Phntp ; separator=",") AS ?Phenotype)
                    ?Forward_Connection ?Alert ?Citation
    WHERE
    {{
        ?Neuron_IRI rdfs:subClassOf ?type .
        FILTER ((?type = ilxtr:NeuronEBM && REGEX(LCASE(STR(?Neuron_IRI)), 'type')) || (?type = ilxtr:NeuronSparcNlp))

        OPTIONAL {{?Neuron_IRI rdfs:label ?Neuron_Label.}}
        OPTIONAL {{?Neuron_IRI skos:prefLabel ?Neuron_Pref_Label.}}

        OPTIONAL {{?Neuron_IRI ilxtr:hasSomaLocation ?A_IRI.}}
        OPTIONAL {{?Neuron_IRI ilxtr:hasAxonLocation ?C_IRI.}}
        OPTIONAL {{?Neuron_IRI (ilxtr:hasAxonTerminalLocation | ilxtr:hasAxonSensoryLocation) ?B_IRI.}}

        OPTIONAL {{?Neuron_IRI ilxtr:hasPhenotypicSex ?Sex.}}
        OPTIONAL {{?Neuron_IRI ilxtr:literatureCitation ?Citation.}}
        OPTIONAL {{?Neuron_IRI ilxtr:alertNote ?Alert.}}

        OPTIONAL {{?Neuron_IRI ilxtr:isObservedInSpecies ?ObservedIn.}}

        OPTIONAL {{?Neuron_IRI ilxtr:hasForwardConnection ?ForwardConnection.}}

        OPTIONAL {{?Neuron_IRI (ilxtr:hasNeuronalPhenotype |
                                ilxtr:hasFunctionalCircuitRole |
                                ilxtr:hasCircuitRole |
                                ilxtr:hasProjection
                                ) ?Phntp.}}
        FILTER(?Neuron_IRI = {entity})
    }} GROUP BY ?Neuron_IRI ?Neuron_Label ?Neuron_Pref_Label ?ObservedIn ?Sex
        ?Forward_Connection ?Alert ?Citation
"""

NODE_METADATA = """
    SELECT DISTINCT ?label WHERE{{
        VALUES(?node){{({entity})}}
        ?node rdfs:label ?label
    }}
"""

CONNECTIVITY_MODELS = """
    SELECT DISTINCT ?Model_ID WHERE{
        ?Model_ID rdfs:subClassOf ilxtr:NeuronEBM .
        ?Neuron_ID rdfs:subClassOf ?Model_ID
        FILTER (
            ?Model_ID != ilxtr:NeuronApinatSimple &&
                STRSTARTS(STR(?Neuron_ID), STR(ilxtr:))
        )
        FILTER NOT EXISTS {
            ?Model_ID rdfs:subClassOf ilxtr:NeuronApinatSimple .
        }
    }
"""

MODEL_KNOWLEDGE = """
    SELECT DISTINCT ?Neuron_ID ?Reference WHERE{{
        {{
            SELECT ?Neuron_ID ?Reference {{
                VALUES(?entity){{({entity})}}
                ?Neuron_ID rdfs:subClassOf ?entity .
                OPTIONAL {{?Neuron_ID ilxtr:reference ?Reference.}}
            }}
        }}
        UNION
        {{
            SELECT ?Neuron_ID ?Reference {{
                VALUES(?entity){{({entity})}}
                ?Super_Neuron rdfs:subClassOf ?entity .
                ?Neuron_ID rdfs:subClassOf ?Super_Neuron .
                ?Neuron_ID rdfs:subClassOf ilxtr:NeuronEBM .
                OPTIONAL {{?Neuron_ID ilxtr:reference ?Reference.}}
            }}
        }}
    }}
"""

DB_VERSION = f"""
    PREFIX TTL: <{NPO_SOURCE}ttl/>
    SELECT DISTINCT ?versionDate ?SimpleSCKAN WHERE{{
        OPTIONAL{{TTL:npo.ttl owl:versionInfo ?versionDate.}}
    }}
"""

#===============================================================================

def sparql_uri(curie: str) -> str:
    return f'<{NAMESPACES.uri(curie)}>'

def is_node(curie: str) -> bool:
    prefix = NAMESPACES.curie(curie).split(':')[0]
    return prefix in ['UBERON', 'ILX']

#===============================================================================

class NpoSparql:
    def __init__(self):
        self.__sparql = SPARQLWrapper2(NPO_SPARQL_ENDPOINT)
        self.__load_apinatomy_connectivities() # load from file due to incompleteness in NPO
        self.__load_connectivity_paths() # get all connectivity paths promptly

    def query(self, sparql) -> list[dict]:
        self.__sparql.setQuery(sparql)
        return self.__sparql.query().bindings

    @staticmethod
    def __row_as_dict(result_row: dict[str, Value]):
        row_dict = {}
        for column, row_data in result_row.items():
            if row_data.type == 'uri':
                row_dict[column] = NAMESPACES.curie(row_data.value)
            else:
                row_dict[column] = row_data.value
        return row_dict

    @staticmethod
    def __results_as_list(results: list[dict]):
        results_list = []
        for result_row in results:
            results_list.append(NpoSparql.__row_as_dict(result_row))
        return results_list

    @staticmethod
    def __result_as_dict(results: list[dict]):
        if len(results):
            ## could have lots of rows if multiple values for query vars, e.g. citation, species, ...
            return NpoSparql.__row_as_dict(results[0])
        else:
            return {}

    def __connectivity(self, neuron):
        return self.__results_as_list(
            self.query(CONNECTIVITY.format(entity=sparql_uri(neuron))))

    def __metadata(self, neuron):
        return self.__result_as_dict(
            self.query(METADATA.format(entity=sparql_uri(neuron))))

    def __connectivity_models(self):
        return self.__results_as_list(self.query(CONNECTIVITY_MODELS))

    def __model_knowledge(self, model):
        return self.__results_as_list(
            self.query(MODEL_KNOWLEDGE.format(entity=sparql_uri(model))))
    
    def __node_knowledge(self, node):
        return self.__result_as_dict(
            self.query(NODE_METADATA.format(entity=sparql_uri(node))))

    def __db_version(self):
        return self.__result_as_dict(self.query(DB_VERSION))

    def __apinatomy_build(self):
        response = requests.get(NPO_PARTIAL_ORDER_API, timeout=10)
        if response.status_code == 200:
            if len(rs_list:=response.json()) > 0:
                rs_json = rs_list[0]
                return {
                    'sha': rs_json.get('sha', ''),
                    'date': rs_json.get('commit', {}).get('committer', {}).get('date', ''),
                    'path': NPO_PARTIAL_ORDER_PATH
                }
        return {}

    def get_knowledge(self, entity) -> dict:
        knowledge = {
            'id': entity
        }
        if is_node(entity): # it might be UBERON|ILX node
            metadata = self.__node_knowledge(entity)
            knowledge['label'] = metadata.get('label', entity)
            return knowledge
        if len(metadata := self.__metadata(entity)) == 0: # it might be about model knowledge
            model_knowledge = self.__model_knowledge(entity)
            if len(model_knowledge) == 0:
                return {}
            else:
                knowledge['label'] = entity
                knowledge['paths'] = []
                knowledge['references'] = []
                for neuron in model_knowledge:
                    knowledge['paths'] += [{'id': neuron['Neuron_ID'], 'models': neuron['Neuron_ID']}]
                return knowledge
        if 'Neuron_Label' in metadata:
            knowledge['label'] = metadata['Neuron_Label']
        else:
            knowledge['label'] = ''
        knowledge['long-label'] = knowledge['label']
        if 'Phenotype' in metadata:
            knowledge['phenotypes'] = [NAMESPACES.curie(p) for p in metadata['Phenotype'].split(',')]
        if 'ObservedIn' in metadata:
            knowledge['taxon'] = metadata['ObservedIn']
        else:
            knowledge['taxon'] = 'NCBITaxon:40674'      # Default to Mammalia
        if 'Sex' in metadata:
            knowledge['biologicalSex'] = metadata['Sex']
        connectivity = []
        if entity.startswith(NPO_NLP_NEURONS):
            for connection in self.__connectivity(entity):
                if ((node_1 := connection.get('V1')) is not None
                and (node_2 := connection.get('V2')) is not None):
                    connectivity.append(((node_1, ()), (node_2, ())))
            knowledge['connectivity'] = connectivity
        elif entity in self.__apinat_connectivities: # current NPO is not completely cover Apinatomy
            knowledge['connectivity'] = self.__apinat_connectivities.get(entity, [])
        return knowledge

    def __load_apinatomy_connectivities(self):
        # loading partial connectivities from NPO repository
        # due to unvailability in stardog
        response = requests.get(NPO_PARTIAL_ORDER_URL, timeout=10)
        if response.status_code == 200:
            partial_order_text = response.text
        else:
            return

        # functions to parse connectivities
        def parse_connectivities(connectivities, sub_structure, root: str|tuple="blank"):
            for sub_sub in sub_structure:
                adj = (
                    (
                        list(reversed(sub_sub[0]))[0],
                        tuple(list(reversed(sub_sub[0]))[1:]),
                    )
                    if isinstance(sub_sub[0], list)
                    else (sub_sub[0], ())
                )
                if root != ("blank", ()):
                    if root != adj:
                        connectivities += [(root, adj)]
                if len(sub_sub) > 1:
                    parse_connectivities(connectivities, sub_sub[1:], adj)

        # function to filter layer terms, returning filtered_edge
        def filter_layer(connectivity):
            edge = []
            for node in connectivity:
                new_node = []
                for terms in node:
                    if isinstance(terms, tuple):
                        terms = [t for t in terms if t not in EXCLUDED_LAYERS]
                        new_node += [tuple(terms)]
                    else:
                        terms = terms if terms not in EXCLUDED_LAYERS else []
                        new_node += [terms]
                if len(new_node[0]) == 0 and len(new_node[1]) == 0:
                    return []
                elif len(new_node[0]) == 0:
                    new_node = [new_node[1][0], tuple(list(new_node[1])[1:])]
                edge += [tuple(new_node)]
            return tuple(edge)

        self.__apinat_connectivities = {}
        for partial_order in partial_order_text.split("\n\n"):
            if "neuronPartialOrder" in partial_order:
                neuron, nested_structure = partial_order.split(
                    "ilxtr:neuronPartialOrder"
                )
                nested_structure = nested_structure.replace(".", "")
                # replace consecutive space with a single space
                nested_structure = re.sub(
                    r"\s+", " ", nested_structure).strip()
                # adding coma
                pattern = r"\[([^]]+)\]"

                def add_comma(match):
                    elements = match.group(1).strip().split()
                    return "[" + ", ".join(elements) + "]"

                nested_structure = re.sub(pattern, add_comma, nested_structure)
                # Quoting ILX and UBERON
                pattern = r"(ILX:\d+|UBERON:\d+)"
                nested_structure = re.sub(pattern, r'"\1"', nested_structure)
                # Specifying tuple
                nested_structure = nested_structure.replace(" )", ", )").replace(
                    " ( ", ", ( "
                )
                # convert to tuple
                conn_structure = ast.literal_eval(nested_structure)
                # parse connectivities
                connectivities = []
                if conn_structure != "blank":
                    if len(conn_structure) > 1:
                        root = (
                            (
                                list(reversed(conn_structure[0]))[0],
                                tuple(list(reversed(conn_structure[0]))[1:]),
                            )
                            if isinstance(conn_structure[0], list)
                            else (conn_structure[0], ())
                        )
                        parse_connectivities(
                            connectivities, conn_structure[1:], root)
                # filter connectivities based on EXCLUDE_LAYERS
                filtered_connectivities = []
                for c in connectivities:
                    edge = filter_layer(c)
                    if len(edge) > 0:
                        if edge[0] != edge[1]:
                            filtered_connectivities += [edge]
                self.__apinat_connectivities[neuron.strip()] = filtered_connectivities

    def __load_connectivity_paths(self):
         models = {}
         for rst in self.__connectivity_models():
             for neuron in self.__model_knowledge(rst['Model_ID']):
                 models[neuron['Neuron_ID']] = {"label": "", "version": ""}
         self.__connectivity_paths = models

    def connectivity_models(self):
        models = {}
        for rst in self.__connectivity_models():
            models[rst['Model_ID']] = {"label": "", "version": ""}
        return models

    def connectivity_paths(self):
        return self.__connectivity_paths

    def build(self):
        builds = self.__apinatomy_build()
        builds['released'] = self.__db_version()['versionDate']
        return builds

#===============================================================================
