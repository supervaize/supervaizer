#!/usr/bin/env python3
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import logging

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()], level=0)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).handlers = [InterceptHandler()]

"""
Supervaizer Server with Admin Interface
"""

import os

from rich.console import Console

from supervaizer.agent import Agent, AgentMethod, AgentMethods
from supervaizer.server import Server

console = Console()


def main() -> None:
    """Start the Supervaizer server with admin interface."""

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
        Agent(
            name="Another Agent",
            description="This is another agent for testing admin interface",
            version="1.3",
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

    # Create server with admin interface enabled
    server = Server(
        agents=agents,
        host=os.getenv("SUPERVAIZER_HOST", "0.0.0.0"),
        port=int(os.getenv("SUPERVAIZER_PORT", 8000)),
        debug=True,
        reload=False,  # Set to False to avoid uvicorn import string issue
        api_key="admin-secret-key-123",  # Required for admin interface
    )

    console.print("🚀 Starting Supervaizer Server...")
    console.print(f"📊 Admin Interface: http://{server.host}:{server.port}/admin/")
    console.print("🔑 API Key: admin-secret-key-123")
    console.print(f"📖 API Docs: http://{server.host}:{server.port}/docs")
    console.print("🔄 Auto-reload: Disabled")
    console.print("\nPress CTRL+C to stop the server")

    # Start the server (this uses uvicorn internally)
    server.launch()


if __name__ == "__main__":
    main()
