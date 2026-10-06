import json
from pathlib import Path

from atlasrag.api import create_app
from atlasrag.core.config import Settings

app = create_app(Settings(_env_file=None))
Path("docs/openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")
app.state.telemetry.close()
print("Saved docs/openapi.json")
