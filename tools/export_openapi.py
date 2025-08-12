# export_openapi.py  <-- NEW
import json
import pathlib
from supervaizer.examples.controller_template import sv_server

app = sv_server.app
# OPTIONAL: tweak metadata/servers before export
app.title = "Supervaize API"  # <- change
# app.servers = [{"url": "https://api.supervaize.com"}]  # <- change

spec = app.openapi()
pathlib.Path("docs/api").mkdir(parents=True, exist_ok=True)
pathlib.Path("docs/api/openapi.json").write_text(json.dumps(spec, indent=2))
