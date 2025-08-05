#!/usr/bin/env python3
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Supervaizer Server with Admin Interface and Auto-reload
Use this if you want auto-reload functionality during development
"""

from supervaizer.agent import Agent, AgentMethod, AgentMethods
from supervaizer.server import Server

# Create basic agent methods (minimal demo implementation)
basic_method = AgentMethod(
    name="Demo Method",
    method="demo.placeholder_method",  # This would be your actual method
    description="Demo method for admin interface testing",
)

# Create demo agents with required methods
agents = [
    Agent(
        name="demo_agent",
        description="Demo agent for testing admin interface",
        version="1.0.0",
        methods=AgentMethods(
            job_start=basic_method,
            job_stop=basic_method,
            job_status=basic_method,
            chat=None,  # Optional
            custom=None,  # Optional
        ),
    ),
    # Add more agents as needed
]

# Create server instance
server = Server(
    agents=agents,
    host="127.0.0.1",
    port=8000,
    debug=True,
    reload=False,  # Must be False when using app object directly
    api_key="admin-secret-key-123",
)

# Export the FastAPI app for uvicorn
app = server.app

if __name__ == "__main__":
    print("🚀 Starting Supervaizer Server with Auto-reload...")
    print("📊 Admin Interface: http://127.0.0.1:8000/admin/")
    print("🔑 API Key: admin-secret-key-123")
    print("📖 API Docs: http://127.0.0.1:8000/docs")
    print("🔄 Auto-reload: Enabled via uvicorn")
    print(
        "\nRunning: uvicorn start_server_with_reload:app --reload --host 127.0.0.1 --port 8000"
    )
    print("Press CTRL+C to stop the server\n")

    # Use uvicorn directly with import string for reload
    import uvicorn

    uvicorn.run(
        "start_server_with_reload:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )
