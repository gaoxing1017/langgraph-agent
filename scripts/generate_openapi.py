#!/usr/bin/env python
"""Generate OpenAPI spec and write to docs/openapi.json."""
from __future__ import annotations

import json
from pathlib import Path

from agent_framework.api.app import create_app

app = create_app()
spec = app.openapi()

output_path = Path(__file__).parent.parent / "docs" / "openapi.json"
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(spec, indent=2))
print(f"OpenAPI spec written to {output_path}")
