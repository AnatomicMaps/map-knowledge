#===============================================================================
#
#  Flatmap viewer and annotation tools
#
#  Copyright (c) 2019-24  David Brooks
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

__version__ = "0.19.2"

#===============================================================================

import sqlite3
import json
import os
from pathlib import Path
from typing import Any, Optional

#===============================================================================

from .apinatomy import CONNECTIVITY_ONTOLOGIES, APINATOMY_MODEL_PREFIX
# from .nposparql import NpoSparql, NPO_NLP_NEURONS
from .npo import Npo
from .scicrunch import SCICRUNCH_PRODUCTION, SCICRUNCH_STAGING
from .scicrunch import SciCrunch
from .utils import log

#===============================================================================

KNOWLEDGE_BASE = 'knowledgebase.db'

#===============================================================================

SCHEMA_VERSION = '1.3'

KNOWLEDGE_SCHEMA = f"""
    create table metadata (name text primary key, value text);

    create table knowledge (source text, entity text, knowledge text);
    create unique index knowledge_index on knowledge(source, entity);

    create table labels (entity text primary key, label text);
    create unique index labels_index on labels(entity);

    create table publications (source text, entity text, publication text);
    create index publications_entity_index on publications(entity);
    create index publications_publication_index on publications(publication);

    create table connectivity_models (model text primary key, version text);

    create table pmr_models (term text, score number, model text, workspace text, exposure text);
    create index pmr_models_term_index on pmr_models(term, score);

    create table connectivity_nodes (source text, node text, path text);
    create unique index connectivity_nodes_index on connectivity_nodes(source, node, path);

    insert into metadata (name, value) values ('schema_version', '{SCHEMA_VERSION}');
"""

SCHEMA_UPGRADES = {
    None: ('1.1', """
        alter table connectivity_models add version text;
        replace into metadata (name, value) values ('schema_version', '1.1');
    """),
    '1.1': ('1.2', """
        create table pmr_models (term text, score number, model text, workspace text, exposure text);
        create index pmr_models_term_index on pmr_models(term, score);
        replace into metadata (name, value) values ('schema_version', '1.2');
    """),
    '1.2': ('1.3', """
        create table knowledge_copy (source text, entity text, knowledge text);
        insert into knowledge_copy (source, entity, knowledge) select null, entity, knowledge from knowledge;
        drop table knowledge;
        alter table knowledge_copy rename to knowledge;
        create unique index knowledge_index on knowledge(source, entity);
        alter table publications add source text;
        create table connectivity_nodes (source text, node text, path text);
        create unique index connectivity_nodes_index on connectivity_nodes(source, node, path);
        replace into metadata (name, value) values ('schema_version', '1.3');
    """)
}

#===============================================================================

class KnowledgeBase(object):
    def __init__(self, store_directory, read_only=False, create=False, knowledge_base=KNOWLEDGE_BASE):
        self.__db = None
        self.__read_only = read_only
        if store_directory is None:
            self.__db_name = None
        else:
            # Create store directory if it doesn't exist
            if not os.path.exists(store_directory):
                os.makedirs(store_directory)
            # Create knowledge base if it doesn't exist and we are allowed to
            self.__db_name = Path(store_directory, knowledge_base).resolve()
            if not self.__db_name.exists():
                if not create:
                    raise IOError(f'Missing KnowledgeBase: {self.__db_name}')
                db = sqlite3.connect(self.__db_name, autocommit=False,
                    detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
                db.executescript(KNOWLEDGE_SCHEMA)
                db.commit()
                db.close()
            self.open(read_only=read_only)

    @property
    def db(self):
        return self.__db

    @property
    def db_name(self):
        return self.__db_name

    @property
    def read_only(self):
        return self.__read_only

    def close(self):
        if self.__db is not None:
            self.__db.close()
            self.__db = None

    def open(self, read_only=False):
        self.close()
        if self.__db_name is not None:
            db_uri = f'{self.__db_name.as_uri()}?mode=ro' if read_only else self.__db_name.as_uri()
            self.__db = sqlite3.connect(db_uri, uri=True, autocommit=False,
                                        detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            if self.__db is not None:
                if (schema_version := self.metadata('schema_version')) != SCHEMA_VERSION:
                    if read_only:
                        raise ValueError(f'Knowledge base schema requires an upgrade from version {schema_version} but opened read only...')
                    while schema_version != SCHEMA_VERSION:
                        if (upgrade := SCHEMA_UPGRADES.get(schema_version)) is None:
                            raise ValueError(f'Unable to upgrade knowledge base schema from version {schema_version}')
                        log.warn(f'Upgrading knowledge base schema from version {schema_version} to {upgrade[0]}')
                        schema_version = upgrade[0]
                        try:
                            self.__db.executescript(upgrade[1])
                        except sqlite3.Error as e:
                            self.__db.rollback()
                            raise ValueError(f'Unable to upgrade knowledge base schema to version {schema_version}: {str(e)}')
                        self.__db.commit()

    def metadata(self, name):
        if self.__db is not None:
            row = self.__db.execute('select value from metadata where name=?', (name,)).fetchone()
            if row is not None:
                return row[0]

    def set_metadata(self, name, value):
        if self.__db is not None:
            self.__db.execute('replace into metadata values (?, ?)', (name,value))
            self.__db.commit()

#===============================================================================

class KnowledgeStore(KnowledgeBase):
    def __init__(self, store_directory=None,
                       knowledge_base=KNOWLEDGE_BASE,
                       create=True,
                       read_only=False,
                       clean_connectivity=False,
                       knowledge_source=None,
                       scicrunch_key=None,
                       scicrunch_version=SCICRUNCH_PRODUCTION,
                       sckan_version: Optional[str]=None,
                       sckan_provenance=False,
                       use_sckan=True,
                       verbose=True):
        super().__init__(store_directory, create=create, knowledge_base=knowledge_base, read_only=read_only)
        self.__entity_knowledge: dict[tuple[Optional[str], str], dict[str, Any]] = {}     # Cache lookups
        self.__npo_entities: set[str] = set()
        self.__sckan_provenance: dict[str, Optional[str]|dict[str, str]] = {}
        self.__verbose = verbose

        if (db_name := self.db_name) is not None:
            cache_msg = f'with cache {db_name}'
        else:
            cache_msg = f'with no cache'
        if verbose:
            log.info(f'Map Knowledge version {__version__} {cache_msg}')

        if not read_only:
            if  knowledge_source is not None:
                raise ValueError('Cannot specify `knowledge_source` when getting knowledge from SCKAN')
        elif self.db is None:
            raise ValueError('Knowledge unavailable as local store nor SCKAN connection is provided')

        self.__source = None
        self.__scicrunch = (None if (read_only or not use_sckan)
                       else SciCrunch(scicrunch_release=scicrunch_version, scicrunch_key=scicrunch_key))
        if self.__scicrunch is not None and sckan_provenance:
            sckan_build = self.__scicrunch.build()
            if sckan_build is not None:
                self.__source = f'{sckan_build["released"]}-sckan'
                if sckan_provenance:
                    self.__sckan_provenance['scicrunch'] = {
                        'url': self.__scicrunch.api_endpoint,
                        'date': sckan_build['released']
                    }
            if verbose and sckan_provenance:
                scicrunch_build = (f" built at {sckan_build['released']}" if sckan_build is not None else '')
                release_version = 'production' if scicrunch_version == SCICRUNCH_PRODUCTION else 'staging'
                log.info(f"With {release_version} SCKAN{scicrunch_build} from {self.__scicrunch.api_endpoint}")

        if not read_only and use_sckan:
            self.__npo_db = Npo(sckan_version)
            self.__npo_entities = set(self.__npo_db.connectivity_paths())
            self.__npo_entities.update(self.__npo_db.connectivity_models())
            if sckan_provenance:
                npo_builds = self.__npo_db.build()
                if len(npo_builds):
                    self.__sckan_provenance['npo'] = {
                            'date': npo_builds['released'],
                            'release': npo_builds['release'],
                            'path': npo_builds['path'],
                            'sha': npo_builds['sha']
                    }
                    if verbose:
                        log.info(f"With NPO built at {npo_builds['released']} from {npo_builds['path']}, SHA: {npo_builds['sha']}")
            self.__source = f'{self.__npo_db.release}-npo'
        else:
            self.__npo_db = None

        if self.__source is None and self.db:
            if knowledge_source is None:
                row = self.db.execute('select distinct source from knowledge order by source desc').fetchone()
                if row is not None:
                    self.__source = row[0]
            elif knowledge_source not in self.knowledge_sources():
                raise ValueError(f'Unknown knowledge source: `{knowledge_source}`')
            else:
                self.__source = knowledge_source
        if self.__source:
            self.__sckan_provenance['knowledge-source'] = self.__source

        if verbose:
            log.info(f'Using knowledge source: {self.__source}')

        # Optionally clear local connectivity knowledge
        if clean_connectivity:
            self.clean_connectivity(self.__source)

    @property
    def source(self):
        return self.__source

    @property
    def sckan_provenance(self):
        return self.__sckan_provenance

    def clean_connectivity(self, knowledge_source):
    #==============================================
        if self.db is not None and knowledge_source is not None:
            if self.__verbose:
                log.info(f'Clearing connectivity knowledge for `{knowledge_source}`...')
            namespaces = [f'{APINATOMY_MODEL_PREFIX}%']
            namespaces.extend([f'{ontology}:%' for ontology in CONNECTIVITY_ONTOLOGIES])
            condition = ' or '.join(len(namespaces)*['entity like ?'])
            params = [knowledge_source] + namespaces
            self.db.execute(f'delete from knowledge where source=? and ({condition})', tuple(params))
            self.db.execute(f'delete from connectivity_nodes where source=?', (knowledge_source,))
            self.db.commit()

    def connectivity_models(self) -> list[str]:
    #==========================================
        """
        Get URIs of connectivity models held in the NPO knowledge source.

        :returns:   A list of model URIs
        """
        if self.__npo_db is not None:
            # Future: need to warn when NPO has been updated and make sure user
            #         clears the cache...
            return self.__npo_db.connectivity_models()
        else:
            log.warning('NPO connectivity models requested but no connection to NPO service')
        return []

    def connectivity_paths(self, connected_only=True) -> list[str]:
    #=========================================
        """
        Get URIs of connectivity paths held in the NPO knowledge source.

        :returns:   A list of path URIs
        """
        if self.__npo_db is not None:
            # Future: need to warn when NPO has been updated and make sure user
            #         clears the cache...
            return self.__npo_db.connectivity_paths(connected_only)
        else:
            log.warning('NPO connectivity paths requested but no connection to NPO service')
        return []

    def labels(self):
    #================
        if self.db is not None:
            return [tuple(row) for row in self.db.execute('select entity, label from labels order by entity')]
        else:
            return []

    @staticmethod
    def __log_errors(entity, knowledge):
    #===================================
        for error in knowledge.get('errors', []):
            log.error(f'SCKAN knowledge error: {entity}: {error}')

    def entity_knowledge(self, entity: str, source=None):
    #====================================================
        use_source = self.__source if source is None else source

        # Check local cache
        if (knowledge := self.__entity_knowledge.get((use_source, entity))) is not None:
            KnowledgeStore.__log_errors(entity, knowledge)
            return knowledge

        knowledge = {}
        if self.db is not None:
            # Check our database
            if use_source is not None:
                row = self.db.execute('select source, knowledge from knowledge where source=? and entity=?',
                                                                            (use_source, entity)).fetchone()
            else:
                row = self.db.execute('select source, knowledge from knowledge where entity=? order by source desc',
                                                                            (entity,)).fetchone()
            if row is not None:
                knowledge = json.loads(row[1])
                knowledge['source'] = row[0]

        if ((len(knowledge) == 0 or entity == knowledge.get('label', entity))
        and (source is None or source == self.__source)):
            # We don't have knowledge or a valid label for the entity so check SCKAN
            ontology = entity.split(':')[0]
            if entity in self.__npo_entities or ontology in CONNECTIVITY_ONTOLOGIES:
                # Always consult NPO for connectivity or if we know it has the term
                if self.__verbose:
                    log.info(f'Consulting NPO for knowledge about {entity}')
                if self.__npo_db:
                    knowledge = self.__npo_db.get_knowledge(entity)
            elif self.__scicrunch is not None:
                # Otherwise consult Scicrunch
                if self.__verbose:
                    log.info(f'Consulting SciCrunch for knowledge about {entity}')
                knowledge = self.__scicrunch.get_knowledge(entity)
                if 'connectivity' in knowledge:
                    # Get phenotype, taxon, and other metadata
                    knowledge.update(self.__scicrunch.connectivity_metadata(entity))

            knowledge['source'] = self.__source
            if len(knowledge) > 1 and self.db is not None and not self.read_only:
                # Use 'long-label' if the entity's label' is the same as itself.
                if 'label' in knowledge:
                    if knowledge['label'] == entity and 'long-label' in knowledge:
                        knowledge['label'] = knowledge['long-label']                # Save knowledge in our database
                self.db.execute('replace into knowledge (source, entity, knowledge) values (?, ?, ?)',
                                                    (self.__source, entity, json.dumps(knowledge)))
                # Save label and references in their own tables
                if 'label' in knowledge:
                    self.db.execute('replace into labels values (?, ?)', (entity, knowledge['label']))
                if 'references' in knowledge:
                    self.__update_references(entity, knowledge.get('references', []))

                connectivity_terms = set()
                if 'connectivity' in knowledge:
                    seen_nodes = set()
                    for edge in knowledge['connectivity']:
                        for node in edge:
                            if node not in seen_nodes:
                                seen_nodes.add(node)
                                self.db.execute('replace into connectivity_nodes (source, node, path) values (?, ?, ?)',
                                                                              (self.__source, json.dumps(node), entity))
                                connectivity_terms.update([node[0]] + list(node[1]))

                # Finished entity specific updates so commit transaction
                self.db.commit()

                # Now make sure we have knowledge for each entity used for connectivity
                for term in connectivity_terms:
                    self.entity_knowledge(term)

        # Use the entity's value as its label if none is defined
        if 'label' not in knowledge:
            knowledge['label'] = entity

        # Cache local knowledge
        if 'source' in knowledge:
            self.__entity_knowledge[(knowledge['source'], entity)] = knowledge

        # Log any errors
        KnowledgeStore.__log_errors(entity, knowledge)

        return knowledge

    def knowledge_sources(self) -> list[str]:
    #========================================
        return ([row[0]
                    for row in self.db.execute(
                        'select distinct source from knowledge order by source desc').fetchall()] if self.db
                else [])

    def label(self, entity):
    #=======================
        if self.db is not None:
            row = self.db.execute('select label from labels where entity=?', (entity,)).fetchone()
            if row is not None:
                return row[0]
        knowledge = self.entity_knowledge(entity)
        return knowledge['label']

    def __update_references(self, entity, references):
    #=================================================
        if self.db is not None:
            with self.db:
                self.db.execute('delete from publications where source=? and entity=?', (self.__source, entity, ))
                self.db.executemany('insert into publications(source, entity, publication) values (?, ?, ?)',
                    ((self.__source, entity, reference) for reference in references))

    def extract_knowledge(self) -> dict:
        """
        Get JSON knowledge of terms in the NPO knowledge source.

        :returns:   A ditionary of terms
        """
        if self.__npo_db is not None:
            # Future: need to warn when NPO has been updated and make sure user
            #         clears the cache...
            return self.__npo_db.extracted_knowledge()
        else:
            log.warning('NPO knowledge terms requested but no connection to NPO service')
        return dict()

#===============================================================================
