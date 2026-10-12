from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_migration_preserves_existing_data_in_private_legacy_scope(tmp_path: Path) -> None:
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path}/legacy.db"
    config.set_main_option("sqlalchemy.url", url)
    # env.py obtains the URL from Settings, so pass a non-secret isolated test database.
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"ATLAS_DATABASE_URL": url}):
        command.upgrade(config, "0001")
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(
                text("""
                INSERT INTO documents (id,title,source,format,status,chunking,tags,raw,
                                       content_hash,created_at)
                VALUES ('legacy-doc','Original PDF','','pdf','ready','semantic','[]',
                        X'25504446','hash',CURRENT_TIMESTAMP)
            """)
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            row = connection.execute(text("SELECT title, workspace_id FROM documents")).one()
            assert row == ("Original PDF", "legacy")
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                == "0002"
            )
        engine.dispose()


def test_hosted_upgrade_is_idempotent_and_version_checked(tmp_path: Path) -> None:
    import os
    from unittest.mock import patch

    from atlasrag.core.schema import upgrade_hosted_workspace

    url = f"sqlite:///{tmp_path}/hosted.db"
    config = Config("alembic.ini")
    with patch.dict(os.environ, {"ATLAS_DATABASE_URL": url}):
        command.upgrade(config, "0001")
    engine = create_engine(url)
    with engine.begin() as connection:
        upgrade_hosted_workspace(connection)
        upgrade_hosted_workspace(connection)
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"
        )
    engine.dispose()
