import time

import httpx

from atlasrag.core.config import Settings


def main() -> None:
    settings = Settings()
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        timeout=60,
        headers={"X-API-Key": settings.api_key.get_secret_value()},
    ) as client:
        client.get("/ready").raise_for_status()
        created = client.post(
            "/documents",
            json={
                "title": "Atlas smoke test",
                "content": (
                    "# Verification\nA smoke test verifies that asynchronous "
                    "ingestion and retrieval work."
                ),
            },
        )
        created.raise_for_status()
        document_id = created.json()["id"]
        try:
            for _ in range(60):
                doc = client.get(f"/documents/{document_id}")
                doc.raise_for_status()
                if doc.json()["document"]["status"] == "ready":
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Ingestion did not become ready within 60 seconds")
            answer = client.post(
                "/query",
                json={
                    "question": "What does a smoke test verify?",
                    "filters": {"document_ids": [document_id]},
                },
            )
            answer.raise_for_status()
            assert answer.json()["citations"], answer.json()
            assert all(c["document_id"] == document_id for c in answer.json()["citations"])
            print("Smoke passed: readiness, ingestion, retrieval, citations and deletion.")
        finally:
            client.delete(f"/documents/{document_id}").raise_for_status()


if __name__ == "__main__":
    main()
