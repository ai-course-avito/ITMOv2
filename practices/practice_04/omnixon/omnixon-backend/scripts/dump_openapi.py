"""Write the OpenAPI schema of the API to a file (default: stdout).

The omnixon-lib tests compare their models with this snapshot, so regenerate it
whenever a request or response model changes:

    uv run python scripts/dump_openapi.py ../omnixon-lib/tests/server_openapi.json
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("POSTGRES_PORT", "0")  # the app is only imported, never started
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from main import app  # noqa: E402

schema = json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(schema)
else:
    sys.stdout.write(schema)
