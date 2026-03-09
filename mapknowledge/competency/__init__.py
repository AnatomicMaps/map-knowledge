#===============================================================================
#
#  Flatmap viewer and annotation tools
#
#  Copyright (c) 2019-25  David Brooks
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

from dataclasses import dataclass
import json
from typing import Any, LiteralString, Optional

#===============================================================================

import psycopg as pg
from tqdm import tqdm

#===============================================================================

from mapknowledge import clean_knowledge_source, NERVE_TYPE

#===============================================================================
#===============================================================================

NODE_PHENOTYPES = [
    'ilxtr:hasSomaLocatedIn',
    'ilxtr:hasAxonPresynapticElementIn',
    'ilxtr:hasAxonSensorySubcellularElementIn',
    'ilxtr:hasAxonLeadingToSensorySubcellularElementIn',
    'ilxtr:hasAxonLocatedIn',
    'ilxtr:hasDendriteLocatedIn',
]
NODE_TYPES = [
   NERVE_TYPE,
]

#===============================================================================
#===============================================================================

@dataclass
class KnowledgeSource:
    source_id: str
    sckan_id: str
    description: Optional[str] = None

    def __post_init__(self):
        self.source_id = clean_knowledge_source(self.source_id)
        self.sckan_id = clean_knowledge_source(self.sckan_id)

#===============================================================================

type KnowledgeDict = dict[str, Any]

#===============================================================================

class KnowledgeList:
    def __init__(self, source: KnowledgeSource, knowledge: Optional[list[KnowledgeDict]]=None):
        self.__source = source
        if knowledge is None:
            self.__knowledge: list[KnowledgeDict] = []
        else:
            self.__knowledge = knowledge

    @property
    def source(self) -> KnowledgeSource:
        return self.__source

    @property
    def knowledge(self) -> list[KnowledgeDict]:
        return self.__knowledge

    def append(self, knowledge: KnowledgeDict):
        self.__knowledge.append(knowledge)

#===============================================================================
#===============================================================================

class CompetencyDatabase:
    def __init__(self, user: Optional[str], host: str, database: str):
        pg_user = f'{user}@' if user else ''
        self.__db = pg.connect(f'postgresql://{pg_user}{host}/{database}')

    def close(self):
    #===============
        if self.__db is not None:
            self.__db.close()
            self.__db = None

    def execute(self, sql: LiteralString, params: Optional[tuple|list]):
    #===================================================================
        if self.__db is not None:
            return self.__db.execute(sql, params)

    def import_knowledge(self, knowledge: KnowledgeList, update_types: bool=False, show_progress=False):
    #===================================================================================================
        if self.__db is not None:
            with self.__db.cursor() as cursor:
                try:
                    self.__delete_source_from_tables(cursor, knowledge.source)
                    if update_types:
                        self.__update_anatomical_types(cursor)
                    ## Use tqdm to show progress...
                    self.__update_knowledge_source(cursor, knowledge.source)
                    self.__update_features(cursor, knowledge)
                    self.__update_connectivity(cursor, knowledge, show_progress)

                    self.__db.commit()
                except:
                    self.__db.rollback()
                    raise

    def __delete_source_from_tables(self, cursor, source: KnowledgeSource):
    #======================================================================
        source_id = source.source_id
        cursor.execute('DELETE FROM path_taxons WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM feature_evidence WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM path_edges WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM path_features WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM path_node_features WHERE source_id=%s', (source_id,  ))
        cursor.execute('DELETE FROM path_forward_connections WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM path_node_types WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM path_phenotypes WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM path_properties WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM path_node_mappings WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM path_node_mappings WHERE sckan_id=%s', (source_id, ))
        cursor.execute('DELETE FROM path_nodes WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM feature_types WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM feature_expert_consultants WHERE source_id=%s', (source_id, ))
        cursor.execute('DELETE FROM feature_terms WHERE source_id=%s', (source_id, ))

    def __update_anatomical_types(self, cursor):
    #===========================================
        cursor.execute('''DELETE FROM anatomical_types at
                            WHERE (NOT EXISTS (SELECT 1 FROM feature_types ft WHERE at.type_id = ft.type_id))
                              AND (NOT EXISTS (SELECT 1 FROM path_node_types pnt WHERE at.type_id = pnt.type_id))''')
        cursor.executemany('INSERT INTO anatomical_types (type_id, label) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                           [(type, type) for type in NODE_PHENOTYPES + NODE_TYPES])

    def __update_connectivity(self, cursor, knowledge: KnowledgeList, show_progress=False):
    #======================================================================================
        source_id = knowledge.source.source_id
        if show_progress:
            progress_bar = tqdm(total=len(knowledge.knowledge),
                unit='records', ncols=80,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}')
        else:
            progress_bar = None

        for record in knowledge.knowledge:
            if source_id == clean_knowledge_source(record.get('source', '')):
                if (connectivity := record.get('connectivity')) is not None:
                    path_id = record['id']

                    # Taxons
                    taxons = record.get('taxons', ['NCBITaxon:40674'])
                    cursor.executemany('INSERT INTO taxons (taxon_id) VALUES (%s) ON CONFLICT DO NOTHING',
                                       ((taxon,) for taxon in taxons))

                    # Path taxons
                    with cursor.copy("COPY path_taxons (source_id, path_id, taxon_id) FROM STDIN") as copy:
                        for taxon in taxons:
                            copy.write_row((source_id, path_id, taxon))

                    # Evidence
                    evidence = record.get('references', [])
                    cursor.executemany('INSERT INTO evidence (evidence_id) VALUES (%s) ON CONFLICT DO NOTHING',
                                       ((evidence,) for evidence in evidence))

                    # Path evidence
                    with cursor.copy("COPY feature_evidence (source_id, term_id, evidence_id) FROM STDIN") as copy:
                        for evidence_id in evidence:
                            copy.write_row((source_id, path_id, evidence_id))

                    # Nodes
                    nodes = set(json.dumps(node) for (node, _) in connectivity) | set(json.dumps(node) for (_, node) in connectivity)
                    cursor.executemany('INSERT INTO path_nodes (source_id, path_id, node_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING',
                                       ((source_id, path_id, node,) for node in nodes))

                    # Node features
                    node_features = [ (source_id, path_id, node, feature)
                                            for (node, features) in [(node, json.loads(node)) for node in nodes]
                                                for feature in [features[0]] + features[1] ]
                    cursor.executemany('INSERT INTO path_node_features (source_id, path_id, node_id, feature_id) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING',
                                        node_features)

                    # Path edges
                    path_nodes = [ (source_id, path_id, json.dumps(node_0), json.dumps(node_1)) for (node_0, node_1) in connectivity ]
                    with cursor.copy("COPY path_edges (source_id, path_id, node_0, node_1) FROM STDIN") as copy:
                        for row in path_nodes:
                            copy.write_row(row)

                    # Path features
                    path_features = [(source_id, path_id, feature) for feature in set([nf[3] for nf in node_features])]
                    with cursor.copy("COPY path_features (source_id, path_id, feature_id) FROM STDIN") as copy:
                        for row in path_features:
                            copy.write_row(row)

                    # Forward connections
                    forward_connections = [(source_id, path_id, forward_path) for forward_path in record.get('forward-connections', [])]
                    with cursor.copy("COPY path_forward_connections (source_id, path_id, forward_path_id) FROM STDIN") as copy:
                        for row in forward_connections:
                            copy.write_row(row)

                    # Path node types
                    node_types = []
                    node_phenotypes = record.get('node-phenotypes', {})
                    for type, nodes in node_phenotypes.items():
                        node_types.extend([(source_id, path_id, json.dumps(node), type)
                                                for node in nodes])
                    node_types.extend([(source_id, path_id, json.dumps(node), NERVE_TYPE)
                                            for node in record.get('nerves', [])])
                    with cursor.copy("COPY path_node_types (source_id, path_id, node_id, type_id) FROM STDIN") as copy:
                        for row in node_types:
                            copy.write_row(row)

                    # Path phenotypes
                    with cursor.copy("COPY path_phenotypes (source_id, path_id, phenotype) FROM STDIN") as copy:
                        for phenotype in record.get('phenotypes', []):
                            copy.write_row((source_id, path_id, phenotype))

                    # General path properties
                    cursor.execute('INSERT INTO path_properties (source_id, path_id, biological_sex, alert, disconnected) VALUES (%s, %s, %s, %s, %s)',
                                       (source_id, path_id, record.get('biologicalSex'), record.get('alert'), record.get('pathDisconnected', False)))

                    # Node mappings
                    node_mappings = [ (source_id, path_id, json.dumps(node), knowledge.source.sckan_id, json.dumps(sckan_node))
                                            for (node, sckan_node) in record.get('node-mappings', []) ]
                    cursor.executemany('INSERT INTO path_node_mappings (source_id, path_id, node_id, sckan_id, sckan_node_id) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING',
                                        node_mappings)

                    # Expert consultants
                    expert_consultants = record.get('expert-consultants', [])
                    cursor.executemany('INSERT INTO expert_consultants (expert_id) VALUES (%s) ON CONFLICT DO NOTHING',
                                       ((expert,) for expert in expert_consultants))

                    # Path expert consultants
                    with cursor.copy("COPY feature_expert_consultants (source_id, term_id, expert_id) FROM STDIN") as copy:
                        for expert in expert_consultants:
                            copy.write_row((source_id, path_id, expert))

            if progress_bar is not None:
                progress_bar.update(1)
        if progress_bar is not None:
            progress_bar.close()

    def __update_features(self, cursor, knowledge: KnowledgeList):
    #=============================================================
        source_id = knowledge.source.source_id
        cursor.execute('DELETE FROM feature_terms WHERE source_id=%s', (source_id, ))

        for record in knowledge.knowledge:
            if source_id == clean_knowledge_source(record.get('source', '')):

                # Feature terms
                with cursor.copy("COPY feature_terms (source_id, term_id, label, description) FROM STDIN") as copy:
                    copy.write_row([source_id, record['id'], record.get('label'), record.get('long-label')])

                # Feature types
                with cursor.copy("COPY feature_types (source_id, term_id, type_id) FROM STDIN") as copy:
                    if (term_type:=record.get('type')) is not None:
                        copy.write_row([source_id, record['id'], term_type])

    def __update_knowledge_source(self, cursor, source: KnowledgeSource):
    #====================================================================
        cursor.execute('''INSERT INTO knowledge_sources (source_id, sckan_id, description)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (source_id) DO UPDATE
                                SET sckan_id = excluded.sckan_id,
                                    description = excluded.description''',
            (source.source_id, source.sckan_id, source.description))

#===============================================================================
#===============================================================================
