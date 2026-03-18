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

__version__ = "1.6.3"

#===============================================================================

import sqlite3
import json
import os
from pathlib import Path
from typing import Any, Optional

#===============================================================================

import structlog

#===============================================================================

from .anatomical_types import *
from .apinatomy import CONNECTIVITY_ONTOLOGIES, APINATOMY_MODEL_PREFIX
# from .nposparql import NpoSparql, NPO_NLP_NEURONS
from .npo import Npo
from .scicrunch import SCICRUNCH_PRODUCTION, SCICRUNCH_STAGING
from .scicrunch import SciCrunch

try:
    from mapmaker.utils import log as logger    # pyright: ignore[reportMissingImports]
    logger_name = 'mapmaker'
except:
    logger_name = __name__

#===============================================================================

KNOWLEDGE_BASE = 'knowledgebase.db'

#===============================================================================

SCHEMA_VERSION = '1.4'

## Have auto update to remove any ``-npo`` suffix on ``source`` column values.

## select count(*) from knowledge where substr(source, -4, 4) = '-npo'


## update knowledge set source=substr(source, 1, length(source)-4) where substr(source, -4, 4)='-npo';


## Server needs to then trim any ``-npo`` from ``source`` sent by viewer

## Better for viewer to trim ``source``.



KNOWLEDGE_SCHEMA = f"""
    create table metadata (name text primary key, value text);

    create table knowledge (source text, entity text, knowledge text);
    create unique index knowledge_index on knowledge(source, entity);

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
    """),
    '1.3': ('1.4', """
        drop table labels;
        drop table publications;
        replace into metadata (name, value) values ('schema_version', '1.4');
    """)
}

#===============================================================================

def clean_knowledge_source(source: str) -> str:
    if source.endswith('-npo'):
        return source[:-4]
    return source

#===============================================================================
#===============================================================================

## Add node "aliases" to knowledge store??
##
## This conflates anatomical terms and connectivity nodes...
##
##alias_entry = {
##    "id": ["ILX:0738432", []],
##    "aliases": [
##        ["ILX:0793804", []],
##        ["ILX:0793877", []]
##    ]
##}
## What is being stored? Why? How is it used??
##
## $ curl https://mapcore-demo.org/fccb/flatmap/knowledge/label/ILX:0738432
## {"entity":"ILX:0738432","label":"Sixth lumbar spinal cord segment"}
## $ curl https://mapcore-demo.org/fccb/flatmap/knowledge/label/ILX:0793804
## {"entity":"ILX:0793804","label":"L6 parasympathetic nucleus"}
## $ curl https://mapcore-demo.org/fccb/flatmap/knowledge/label/ILX:0793877
## {"entity":"ILX:0793877","label":"Intermediolateral nucleus of sixth lumbar segment"}


class KnowledgeBase(object):
    def __init__(self, store_directory, read_only=False, create=False, knowledge_base=KNOWLEDGE_BASE):
        logger = structlog.get_logger(logger_name)
        self.__logger = logger.bind(type='knowledge')
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
    def db(self) -> Optional[sqlite3.Connection]:
    #============================================
        return self.__db

    @property
    def log(self) -> structlog.BoundLogger:
    #======================================
        return self.__logger

    @property
    def db_name(self) -> Optional[str]:
    #==================================
        return str(self.__db_name) if self.__db_name is not None else None

    @property
    def read_only(self) -> bool:
    #===========================
        return self.__read_only

    def close(self):
    #===============
        if self.__db is not None:
            self.__db.close()
            self.__db = None

    def open(self, read_only: bool=False):
    #=====================================
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
                        self.log.warning(f'Upgrading knowledge base schema from version {schema_version} to {upgrade[0]}')
                        schema_version = upgrade[0]
                        try:
                            self.__db.executescript(upgrade[1])
                        except sqlite3.Error as e:
                            self.__db.rollback()
                            raise ValueError(f'Unable to upgrade knowledge base schema to version {schema_version}: {str(e)}')
                        self.__db.commit()

    def metadata(self, name: str) -> Optional[str]:
    #==============================================
        if self.__db is not None:
            row = self.__db.execute('select value from metadata where name=?', (name,)).fetchone()
            if row is not None:
                return row[0]

    def set_metadata(self, name: str, value: str):
    #=============================================
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
            self.log.info(f'Map Knowledge version {__version__} {cache_msg}')

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
                self.log.info(f"With {release_version} SCKAN{scicrunch_build} from {self.__scicrunch.api_endpoint}")

        if not read_only and use_sckan:
            self.__npo_db = Npo(sckan_version)
            self.__npo_entities = set(self.__npo_db.terms)
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
                        self.log.info(f"With NPO built at {npo_builds['released']} from {npo_builds['path']}, SHA: {npo_builds['sha']}")
            self.__source = self.__npo_db.release
        else:
            self.__npo_db = None

        if self.__source is None and self.db:
            known_sources= self.knowledge_sources()
            if knowledge_source is None:
                if len(known_sources):
                    self.__source = known_sources[0]
            elif knowledge_source not in known_sources:
                raise ValueError(f'Unknown knowledge source: `{knowledge_source}`')
            else:
                self.__source = clean_knowledge_source(knowledge_source)
        if self.__source:
            self.__sckan_provenance['knowledge-source'] = self.__source

        if verbose:
            self.log.info(f'Using knowledge source: {self.__source}')

        # Optionally clear local connectivity knowledge
        if clean_connectivity:
            self.clean_connectivity(self.__source)

        # Remove `-npo` suffixes used to identify knowledge sources in database tables
        if self.db is not None:
            self.__clean_source_suffix()

    @property
    def source(self):
        return self.__source

    @property
    def sckan_provenance(self):
        return self.__sckan_provenance

    def __log_errors(self, entity: str, knowledge: dict):
    #==============================================
        for error in knowledge.get('errors', []):
            self.log.error(f'SCKAN knowledge error: {entity}: {error}')

    def clean_connectivity(self, knowledge_source: Optional[str]):
    #=============================================================
        if self.db is not None and knowledge_source is not None:
            if self.__verbose:
                self.log.info(f'Clearing connectivity knowledge for `{knowledge_source}`...')
            namespaces = [f'{APINATOMY_MODEL_PREFIX}%']
            namespaces.extend([f'{ontology}:%' for ontology in CONNECTIVITY_ONTOLOGIES])
            condition = ' or '.join(len(namespaces)*['entity like ?'])
            params = [knowledge_source] + namespaces
            self.db.execute(f'delete from knowledge where (source=? or source is null) and ({condition})', tuple(params))
            connectivity_terms = set()
            for row in self.db.execute(
                    f'select distinct node from connectivity_nodes where source=? or source is null', (knowledge_source,)).fetchall():
                node = json.loads(row[0])
                connectivity_terms.update([node[0]] + list(node[1]))
            connectivity_entities = list(connectivity_terms)
            condition = ', '.join(len(connectivity_entities)*'?')
            self.db.execute(f'delete from knowledge where (source=? or source is null) and entity in ({condition})',
                                                            tuple([knowledge_source] + connectivity_entities))
            self.db.execute(f'delete from connectivity_nodes where source=? or source is null', (knowledge_source,))
            self.db.commit()

    ### Is this still relevanty???
    def connectivity_models(self) -> list[str]:
    #==========================================
        """
        Get URIs of connectivity models held in the NPO knowledge source.

        :returns:   A list of model URIs
        """
        if self.__npo_db is not None:
            return self.__npo_db.connectivity_models
        else:
            self.log.warning('NPO connectivity models requested but no connection to NPO service')
        return []

    def connectivity_paths(self) -> list[str]:
    #=========================================
        """
        Get URIs of connectivity paths held in the NPO knowledge source.

        :returns:   A list of path URIs
        """
        if self.__npo_db is not None:
            return self.__npo_db.connectivity_paths
        else:
            self.log.warning('NPO connectivity paths requested but no connection to NPO service')
        return []

    def entities(self) -> list[str]:
    #===============================
        if self.__npo_db is not None:
            return self.__npo_db.terms
        else:
            self.log.warning('NPO terms requested but no connection to NPO service')
        return []

    def entities_of_type(self, anatomical_type: str) -> list[str]:
    #=============================================================
        if self.__npo_db is not None:
            return self.__npo_db.terms_of_type(anatomical_type)
        else:
            self.log.warning('NPO terms requested but no connection to NPO service')
        return []

    def entity_knowledge(self, entity: str, source: Optional[str]=None) -> dict:
    #===========================================================================
        use_source = self.__source if source is None else clean_knowledge_source(source)

        # Check local cache
        if (knowledge := self.__entity_knowledge.get((use_source, entity))) is not None:
            self.__log_errors(entity, knowledge)
            return knowledge

        knowledge = {}
        if self.db is not None:
            # Check our database
            if use_source is not None:
                row = self.db.execute(
                    'select source, knowledge from knowledge where source=? and entity=? order by source desc',
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

            # Always first consult NPO
            if self.__verbose:
                self.log.info(f'Consulting NPO for knowledge about {entity}')
            if self.__npo_db:
                knowledge = self.__npo_db.get_knowledge(entity)

            # If NPO doesn't know about the entity and its not connectivity
            # related we consult SciCrunch
            if (len(knowledge) == 1 and self.__scicrunch is not None
            and not (entity in self.__npo_entities or ontology in CONNECTIVITY_ONTOLOGIES)):
                if self.__verbose:
                    self.log.info(f'Consulting SciCrunch for knowledge about {entity}')
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
        self.__log_errors(entity, knowledge)

        return knowledge

    def knowledge_sources(self) -> list[str]:
    #========================================
        if self.db:
            sources = [clean_knowledge_source(row[0])
                        for row in self.db.execute('select distinct source from knowledge').fetchall()
                            if row[0] is not None]
            return sorted(set(sources), reverse=True)
        return []

    def label(self, entity: str) -> str:
    #===================================
        knowledge = self.entity_knowledge(entity)
        return knowledge.get('label', knowledge['id'])

    def labels(self) -> list[tuple[str, str]]:
    #=========================================
        return [(kn['id'], kn.get('label', kn['id'])) for kn in self.stored_knowledge()]

    def stored_knowledge(self, source: Optional[str]=None) -> list[dict]:
    #====================================================================
        stored_knowledge = []
        source = self.__source if source is None else clean_knowledge_source(source)
        if self.db is not None:
            if source is not None:
                rows = self.db.execute(
                    'select source, entity, knowledge from knowledge where source=? or source is null order by entity, source desc',
                                                                            (source, )).fetchall()
            else:
                rows = self.db.execute('select source, entity, knowledge from knowledge order by entity, source desc').fetchall()
            last_entity = None
            for row in rows:
                if row[1] != last_entity:
                    knowledge = json.loads(row[2])
                    knowledge['source'] = row[0]
                    stored_knowledge.append(knowledge)
                    last_entity = row[1]
        return stored_knowledge

    def __clean_source_suffix(self):
    #===============================
        assert self.db is not None
        if self.metadata('clean-source-suffix') is None:
            self.__clean_table('knowledge', ('source', 'entity',  'knowledge'))
            self.__clean_table('connectivity_nodes', ('source', 'node',  'path'))
            self.set_metadata('clean-source-suffix', '1')
            self.db.commit()

    def __clean_table(self, table: str, columns: tuple[str, str, str]):
    #==================================================================
        assert self.db is not None
        sources = [row[0]
                    for row in self.db.execute(f'select distinct {columns[0]} from {table}').fetchall()
                        if row[0] is not None]
        for source in sources:
            cleaned_source = clean_knowledge_source(source)
            if source != cleaned_source:
                self.db.execute(f"""insert into {table} {columns[0], columns[1], columns[2]}
                    select ?, {columns[1]}, {columns[2]} from {table}
                        where {columns[0]}=? and {columns[1]} not in (
                            select {columns[1]} from {table} where {columns[0]}=?)""",
                    (cleaned_source, source, cleaned_source))

#===============================================================================

