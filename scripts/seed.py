"""Seed authored examples through the same durable ingestion path as uploads."""

from pathlib import Path

from atlasrag.core.config import Settings
from atlasrag.core.models import DocumentCreate
from atlasrag.core.runtime import Runtime
from atlasrag.core.storage import Database
from atlasrag.observability.telemetry import Telemetry


def main() -> None:
    settings = Settings()
    db = Database(settings)
    db.initialize()
    telemetry = Telemetry()
    runtime = Runtime(db, settings, telemetry)
    sources = {doc.source for doc in db.documents()}
    for path in sorted(Path("benchmarks/corpus").glob("*.md")):
        source = f"authored-fixture/{path.name}"
        if source not in sources:
            title = path.read_text().splitlines()[0].removeprefix("# ")
            runtime.ingestion.submit(
                DocumentCreate(
                    title=title,
                    content=path.read_text(),
                    source=source,
                    tags=["demo", "engineering"],
                )
            )
    runtime.ingestion.drain()
    docs = db.documents()
    print(f"Ready documents: {sum(d.status == 'ready' for d in docs)} / {len(docs)}")
    runtime.close()
    db.close()
    telemetry.close()


if __name__ == "__main__":
    main()
