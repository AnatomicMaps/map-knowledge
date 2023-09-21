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

from __future__ import annotations
import os
from typing import Optional
import urllib.parse

#===============================================================================

from .apinatomy import Apinatomy, CONNECTIVITY_ONTOLOGIES, APINATOMY_MODEL_PREFIX
from .apinatomy import PATH_METADATA_QUERY
from .namespaces import NAMESPACES
from .utils import log                  # type: ignore
from .utils import request_json

#===============================================================================

INTERLEX_ONTOLOGIES = ['ILX', 'NLX']

#===============================================================================

SCICRUNCH_API_ENDPOINT = 'https://scicrunch.org/api/1'

#===============================================================================

# Values for SCICRUNCH_RELEASE
SCICRUNCH_PRODUCTION = 'sckan-scigraph'
SCICRUNCH_STAGING = 'sparc-scigraph'

# NB. This may change with a new SCKAN release...
CONNECTIVITY_QUERY = 'neru-7'
CONNECTIVITY_QUERY_NEXT = 'neru-7'

#===============================================================================

SCICRUNCH_INTERLEX_VOCAB = '{API_ENDPOINT}/ilx/search/curie/{TERM}'
SCICRUNCH_SPARC_API = '{API_ENDPOINT}/{SCICRUNCH_RELEASE}'

SCICRUNCH_SPARC_CYPHER = f'{SCICRUNCH_SPARC_API}/cypher/execute.json'
SCICRUNCH_SPARC_VOCAB = f'{SCICRUNCH_SPARC_API}/vocabulary/id/{{TERM}}.json'

SCICRUNCH_SPARC_APINATOMY = f'{SCICRUNCH_SPARC_API}/dynamic/demos/apinat'
SCICRUNCH_MODELS_WITH_VERSION = f'{SCICRUNCH_SPARC_APINATOMY}/graphList.json'
SCICRUNCH_CONNECTIVITY_NEURONS = f'{SCICRUNCH_SPARC_APINATOMY}/{{CONNECTIVITY_QUERY}}/{{NEURON_ID}}.json'
SCICRUNCH_MODEL_REFERENCES = f'{SCICRUNCH_SPARC_APINATOMY}/modelPopulationsReferences/{{MODEL_ID}}.json'

#===============================================================================

# See https://nih-sparc.slack.com/archives/C0261A0L5LJ/p1685468238280209
SCKAN_BUILD_QUERY = 'MATCH (p)-[i:build:id]-(), (p)-[e]-() RETURN i, e'

SCKAN_RELEASE_URL = 'https://github.com/SciCrunch/NIF-Ontology/releases/tag/sckan-{RELEASE_DATE}'
SCKAN_RELEASE_NOTES = 'https://github.com/SciCrunch/sparc-curation/blob/master/docs/sckan/CHANGELOG.org#{RELEASE_DATE}'

#===============================================================================

class SciCrunch(object):
    def __init__(self, api_endpoint=SCICRUNCH_API_ENDPOINT, scicrunch_release=SCICRUNCH_PRODUCTION, scicrunch_key=None):
        self.__api_endpoint = api_endpoint
        self.__scicrunch_release = scicrunch_release
        self.__sparc_api_endpoint = SCICRUNCH_SPARC_API.format(API_ENDPOINT=api_endpoint,
                                                               SCICRUNCH_RELEASE=scicrunch_release)
        self.__connectivity_query = CONNECTIVITY_QUERY if scicrunch_release == SCICRUNCH_PRODUCTION else CONNECTIVITY_QUERY_NEXT
        self.__unknown_entities = []
        self.__scicrunch_key = scicrunch_key if scicrunch_key is not None else os.environ.get('SCICRUNCH_API_KEY')
        if self.__scicrunch_key is None:
            log.warning('Undefined SCICRUNCH_API_KEY: SciCrunch knowledge will not be looked up')

    @property
    def sparc_api_endpoint(self):
        return self.__sparc_api_endpoint

    def query(self, cypher: str, **kwds) -> Optional[dict]:
    #======================================================
        if self.__scicrunch_key is not None:
            params = {
                'api_key': self.__scicrunch_key,
                'limit': 9999,
            }
            params['cypherQuery'] = cypher
            params.update(kwds)
            return request_json(SCICRUNCH_SPARC_CYPHER.format(API_ENDPOINT=self.__api_endpoint,
                                                              SCICRUNCH_RELEASE=self.__scicrunch_release),
                                params=params)

    def build(self):
    #===============
        data = self.query(SCKAN_BUILD_QUERY)
        if data is not None:
            for node in data['nodes']:
                if node['id'] == 'build:prov':
                    release_date = node['meta'].get(NAMESPACES.uri('ilxtr:build/date'))[0]
                    return {
                        'created': node['meta'].get(NAMESPACES.uri('ilxtr:build/datetime'))[0],
                        'released': release_date,
                        'release': SCKAN_RELEASE_URL.format(RELEASE_DATE=release_date),
                        'history': SCKAN_RELEASE_NOTES.format(RELEASE_DATE=release_date),
                    }

    def connectivity_models(self):
    #=============================
        models = {}
        if self.__scicrunch_key is not None:
            params = {
                'api_key': self.__scicrunch_key,
                'limit': 9999,
            }
            data = request_json(SCICRUNCH_MODELS_WITH_VERSION.format(API_ENDPOINT=self.__api_endpoint,
                                                                     SCICRUNCH_RELEASE=self.__scicrunch_release),
                                params=params)
            if data is not None:
                local_to_uri = {
                    edge['obj']: edge['sub']
                        for edge in data['edges']
                            if edge['pred'] == 'apinatomy:hasGraph'}
                for node in data.get('nodes', []):
                    if (version := node['meta'].get(NAMESPACES.uri('apinatomy:version'))) is not None:
                        models[local_to_uri[node['id']]] = {
                            'label': node['lbl'],
                            'version': version[0],
                            }
        return models

    def get_knowledge(self, entity: str) -> dict:
    #============================================
        knowledge = {}
        if self.__scicrunch_key is not None:
            params = {
                'api_key': self.__scicrunch_key,
                'limit': 9999,
            }
            ontology = entity.split(':')[0]
            if   ontology in INTERLEX_ONTOLOGIES:
                data = request_json(SCICRUNCH_INTERLEX_VOCAB.format(API_ENDPOINT=self.__api_endpoint,
                                                                    SCICRUNCH_RELEASE=self.__scicrunch_release,
                                                                    TERM=entity),
                                    params=params)
                if data is not None:
                    knowledge['label'] = data.get('data', {}).get('label', entity)
            elif ontology in CONNECTIVITY_ONTOLOGIES:
                data = request_json(SCICRUNCH_CONNECTIVITY_NEURONS.format(API_ENDPOINT=self.__api_endpoint,
                                                                          SCICRUNCH_RELEASE=self.__scicrunch_release,
                                                                          CONNECTIVITY_QUERY=self.__connectivity_query,
                                                                          NEURON_ID=entity),
                                    params=params)
                if data is not None:
                    knowledge = Apinatomy.neuron_knowledge(entity, data)
            elif entity.startswith(APINATOMY_MODEL_PREFIX):
                data = request_json(SCICRUNCH_MODEL_REFERENCES.format(API_ENDPOINT=self.__api_endpoint,
                                                                      SCICRUNCH_RELEASE=self.__scicrunch_release,
                                                                      MODEL_ID=urllib.parse.quote(entity, '')),
                                    params=params)
                if data is not None:
                    knowledge = Apinatomy.model_knowledge(entity, data)
            else:
                data = request_json(SCICRUNCH_SPARC_VOCAB.format(API_ENDPOINT=self.__api_endpoint,
                                                                 SCICRUNCH_RELEASE=self.__scicrunch_release,
                                                                 TERM=entity),
                                    params=params)
                if data is not None:
                    if len(labels := data.get('labels', [])):
                        knowledge['label'] = labels[0]
                    else:
                        knowledge['label'] = entity
        if len(knowledge) == 0 and entity not in self.__unknown_entities:
            log.warning('Unknown anatomical entity: {}'.format(entity))
            self.__unknown_entities.append(entity)
        return knowledge

    def connectivity_metadata(self, entity: str) -> dict[str, str|list[str]]:
    #========================================================================
        if (data := self.query(PATH_METADATA_QUERY, neuron_id=entity)) is not None:
            return Apinatomy.get_metadata(data)
        elif entity not in self.__unknown_entities:
            log.warning('Unknown anatomical entity: {}'.format(entity))
            self.__unknown_entities.append(entity)
        return {}

#===============================================================================
