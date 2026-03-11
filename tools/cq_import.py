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

import json
import logging
import os

#===============================================================================

from mapknowledge import KnowledgeStore
from mapknowledge.competency import CompetencyDatabase, KnowledgeList, KnowledgeSource

#===============================================================================
#===============================================================================

DEFAULT_STORE = 'knowledgebase.db'

#===============================================================================

COMPETENCY_DATABASE = os.environ.get('COMPETENCY_DATABASE', 'map-knowledge')

COMPETENCY_USER = os.environ.get('COMPETENCY_USER')
COMPETENCY_HOST = os.environ.get('COMPETENCY_HOST', 'localhost:5432')

#===============================================================================

def cq_import(knowledge: KnowledgeList):
#=======================================
    competency_db = CompetencyDatabase(COMPETENCY_USER, COMPETENCY_HOST, COMPETENCY_DATABASE)
    competency_db.import_knowledge(knowledge, True)

#===============================================================================
#===============================================================================

def json_knowledge(args) -> KnowledgeList:
#=========================================
    with open(args.json_file) as fp:
        knowledge = json.load(fp)
    source_id = knowledge['source']
    knowledge = KnowledgeList(KnowledgeSource(source_id=source_id, sckan_id=source_id), knowledge['knowledge'])
    return knowledge

def store_knowledge(args) -> KnowledgeList:
#==========================================
    knowledge_source = args.source
    store = KnowledgeStore(
        store_directory=args.store_directory,
        knowledge_base=args.knowledge_store,
        read_only=True,
        knowledge_source=knowledge_source)
    if store.db is None:
        raise IOError(f'Unable to open knowledge store {args.store_directory}/{args.knowledge_store}')
    if store.source is None:
        raise ValueError(f'No valid knowledge sources in {args.store_directory}/{args.knowledge_store}')
    knowledge = KnowledgeList(KnowledgeSource(source_id=store.source, sckan_id=store.source))
    for row in store.db.execute('select entity, knowledge from knowledge where source=?', (store.source,)).fetchall():
        entity_knowledge = json.loads(row[1])
        entity_knowledge['id'] = row[0]
        knowledge.knowledge.append(entity_knowledge)
    store.close()
    return knowledge


def confirm_import(database_name: str) -> bool:
#=============================================
    print(f'About to import knowledge into database: {database_name}')
    response = input('Proceed with import? [y/N]: ').strip().lower()
    return response in ('y', 'yes')

#===============================================================================
#===============================================================================

def main():
    import argparse

## Add epilog about setting KNOWLEDGE_HOST if different from default of...
## And about KNOWLEDGE_USER (with check to see if it's set)
##
    parser = argparse.ArgumentParser(description='Import SCKAN knowledge into a PostgresQL knowledge store.')
    parser.add_argument('-d', '--debug', action='store_true', help='Show DEBUG log messages')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress INFO log messages')
    subparsers = parser.add_subparsers(title='commands', required=True)

    store_parser = subparsers.add_parser('json', help='Import knowledge from a JSON knowledge file.')
    store_parser.add_argument('json_file', metavar='JSON_FILE', help='SCKAN knowledge saved as JSON')
    store_parser.set_defaults(func=json_knowledge)

    store_parser = subparsers.add_parser('store', help='Import knowledge from a local knowledge store.')
    store_parser.add_argument('--store-directory', required=True, help='Directory containing a knowledge store')
    store_parser.add_argument('--knowledge-store', default=DEFAULT_STORE, help=f'Name of knowledge store file. Defaults to `{DEFAULT_STORE}`')
    store_parser.add_argument('--source', help='Knowledge source to import; defaults to the most recent source in the store.')
    store_parser.set_defaults(func=store_knowledge)

    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif not args.quiet:
        logging.basicConfig(level=logging.INFO)

    logging.info('Database: %s', COMPETENCY_DATABASE)
    if not confirm_import(COMPETENCY_DATABASE):
        logging.warning('Import cancelled by user.')
        return

    cq_import(args.func(args))

#===============================================================================

if __name__ == '__main__':
#=========================
    main()

#===============================================================================
