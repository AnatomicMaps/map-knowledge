#===============================================================================
#
#  Competency database schema upgrade helper
#
#===============================================================================

import argparse
import logging
import os

import psycopg as pg

#===============================================================================

PG_DATABASE = 'map-knowledge'
KNOWLEDGE_USER = os.environ.get('KNOWLEDGE_USER')
KNOWLEDGE_HOST = os.environ.get('KNOWLEDGE_HOST', 'localhost:5432')

COMPETENCY_SCHEMA_VERSION = '1.1'
COMPETENCY_SCHEMA_VERSION_KEY = 'schema_version'

def _fk_constraint_sql(table: str, constraint: str, expression: str) -> str:
    return f"""
    DO $$
    BEGIN
        ALTER TABLE public.{table}
            ADD CONSTRAINT {constraint}
            {expression};
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
    """

SCHEMA_1_1_TABLES = [
    'CREATE TABLE IF NOT EXISTS metadata (name character varying PRIMARY KEY, value text NOT NULL)',
    'CREATE TABLE IF NOT EXISTS path_node_mappings ('
    'source_id character varying NOT NULL, '
    'path_id character varying NOT NULL, '
    'node_id character varying NOT NULL, '
    'sckan_id character varying, '
    'sckan_node_id character varying'
    ')',
    'CREATE TABLE IF NOT EXISTS expert_consultants ('
    'expert_id character varying PRIMARY KEY, '
    'type character varying, '
    'details text'
    ')',
    'CREATE TABLE IF NOT EXISTS feature_expert_consultants ('
    'source_id character varying NOT NULL, '
    'term_id character varying NOT NULL, '
    'expert_id character varying NOT NULL'
    ')',
]

SCHEMA_1_1_FOREIGN_KEYS = [
    ('path_node_mappings', 'pnm_source_fk', 'FOREIGN KEY (source_id) REFERENCES knowledge_sources(source_id)'),
    ('path_node_mappings', 'pnm_path_fk', 'FOREIGN KEY (source_id, path_id) REFERENCES feature_terms(source_id, term_id)'),
    ('path_node_mappings', 'pnm_node_fk', 'FOREIGN KEY (source_id, path_id, node_id) REFERENCES path_nodes(source_id, path_id, node_id)'),
    ('path_node_mappings', 'pnm_sckan_fk', 'FOREIGN KEY (sckan_id) REFERENCES knowledge_sources(source_id)'),
    ('feature_expert_consultants', 'fec_source_fk', 'FOREIGN KEY (source_id) REFERENCES knowledge_sources(source_id)'),
    ('feature_expert_consultants', 'fec_feature_fk', 'FOREIGN KEY (source_id, term_id) REFERENCES feature_terms(source_id, term_id)'),
    ('feature_expert_consultants', 'fec_expert_fk', 'FOREIGN KEY (expert_id) REFERENCES expert_consultants(expert_id)'),
]

COMPETENCY_SCHEMA_UPGRADES: dict[str | None, tuple[str, list[str]]] = {
    None: (
        '1.1',
        [
            *SCHEMA_1_1_TABLES,
            *[_fk_constraint_sql(*fk) for fk in SCHEMA_1_1_FOREIGN_KEYS],
            "INSERT INTO metadata (name, value) VALUES ('schema_version', '1.1') "
            "ON CONFLICT (name) DO UPDATE SET value = excluded.value",
        ],
    ),
}

#===============================================================================


def table_exists(db, table_name: str) -> bool:
    row = db.execute('SELECT to_regclass(%s)', (f'public.{table_name}',)).fetchone()
    return row is not None and row[0] is not None


def schema_version(db) -> str | None:
    if not table_exists(db, 'metadata'):
        return None
    row = db.execute(
        'SELECT value FROM metadata WHERE name=%s',
        (COMPETENCY_SCHEMA_VERSION_KEY,),
    ).fetchone()
    return row[0] if row is not None else None


def schema_upgrade_required(db, required_version: str=COMPETENCY_SCHEMA_VERSION) -> bool:
    return schema_version(db) != required_version


def schema_upgrade_message(db, required_version: str=COMPETENCY_SCHEMA_VERSION) -> str | None:
    current_version = schema_version(db)
    if current_version == required_version:
        return None
    return (
        f'Competency schema version {required_version} is required but database has '
        f'version {current_version}. Run `python tools/cq_upgrade.py` to upgrade the schema.'
    )


def upgrade_schema(db, required_version: str=COMPETENCY_SCHEMA_VERSION):
    current_version = schema_version(db)
    while current_version != required_version:
        if (upgrade := COMPETENCY_SCHEMA_UPGRADES.get(current_version)) is None:
            raise ValueError(
                f'Unable to upgrade competency schema from version {current_version} to {required_version}'
            )
        upgrade_version, statements = upgrade
        try:
            with db.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            db.commit()
        except Exception:
            db.rollback()
            raise
        current_version = upgrade_version


def main():
    parser = argparse.ArgumentParser(
        description='Check and upgrade competency schema version in Postgres.'
    )
    parser.add_argument('-d', '--debug', action='store_true', help='Show DEBUG log messages')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress INFO log messages')
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check schema version and exit with non-zero status if upgrade is needed.',
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif not args.quiet:
        logging.basicConfig(level=logging.INFO)

    pg_user = f'{KNOWLEDGE_USER}@' if KNOWLEDGE_USER else ''
    db = pg.connect(f'postgresql://{pg_user}{KNOWLEDGE_HOST}/{PG_DATABASE}')
    try:
        current_version = schema_version(db)
        logging.info('Current competency schema version: %s', current_version)
        logging.info('Required competency schema version: %s', COMPETENCY_SCHEMA_VERSION)

        if not schema_upgrade_required(db):
            logging.info('Competency schema is up to date.')
            return 0

        if args.check_only:
            message = schema_upgrade_message(db)
            if message is not None:
                logging.warning(message)
            return 1

        logging.info('Upgrading competency schema...')
        upgrade_schema(db)
        logging.info('Competency schema upgraded to version %s.', schema_version(db))
        return 0

    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
