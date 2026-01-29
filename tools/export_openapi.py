# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# export_openapi.py  <-- NEW
import json
import pathlib
from supervaizer.examples.controller_template import sv_server

app = sv_server.app
# OPTIONAL: tweak metadata/servers before export
app.title = "Supervaize API"  # <- change
# app.servers = [{"url": "https://app.supervaize.com"}]  # <- change

spec = app.openapi()
pathlib.Path("docs/api").mkdir(parents=True, exist_ok=True)
pathlib.Path("docs/api/openapi.json").write_text(json.dumps(spec, indent=2))
