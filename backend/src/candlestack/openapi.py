"""Prints the OpenAPI schema as stable JSON: ``python -m candlestack.openapi``.

The snapshot ``docs/openapi.json`` must match this output (a unit test checks). From ``backend/``:

    uv run python -m candlestack.openapi > ../docs/openapi.json
"""

import json
import sys

from candlestack.core import Settings
from candlestack.main import create_app

# The schema carries the app version; a fixed one keeps the snapshot equal in every environment.
SNAPSHOT_VERSION = "snapshot"


def render() -> str:
    app = create_app(Settings(app_version=SNAPSHOT_VERSION))
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    # Bytes, so Windows does not turn the newlines into CRLF.
    sys.stdout.buffer.write(render().encode())
