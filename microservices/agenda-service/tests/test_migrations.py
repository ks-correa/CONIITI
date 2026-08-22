import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_mock_engine


class _EmptyResult:
    def mappings(self):
        return self

    def all(self):
        return []


def _compile_postgresql_migration(direction: str) -> list[str]:
    statements: list[str] = []
    engine = None

    def executor(statement, *multiparams, **params):
        statements.append(str(statement.compile(dialect=engine.dialect)))
        return _EmptyResult()

    engine = create_mock_engine("postgresql+psycopg2://", executor)
    operations = Operations(MigrationContext.configure(engine.connect()))
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0002_agenda_integration.py"
    )
    spec = importlib.util.spec_from_file_location("agenda_migration_0002", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    getattr(module, direction)()
    return statements


def test_agenda_upgrade_compiles_for_postgresql_with_all_asset_slots():
    statements = _compile_postgresql_migration("upgrade")

    assert any(
        "venue_resources" in statement
        and "captions_asset_id" in statement
        and "transcript_asset_id" in statement
        for statement in statements
    )
    assert any(
        "asset_reference_outbox" in statement and "slot" in statement
        for statement in statements
    )


def test_agenda_downgrade_compiles_for_postgresql():
    statements = _compile_postgresql_migration("downgrade")

    assert any("DROP TABLE venue_resources" in statement for statement in statements)
    assert any(
        "DROP INDEX ix_venue_resources_captions_asset_id" in statement
        for statement in statements
    )
    assert any(
        "DROP INDEX ix_venue_resources_transcript_asset_id" in statement
        for statement in statements
    )
