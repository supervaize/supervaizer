#!/usr/bin/env python3
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Test script to demonstrate the admin interface integration.
"""

from supervaizer.agent import Agent, AgentMethod, AgentMethods
from supervaizer.server import Server


def main() -> None:
    """Demo the admin interface."""
    print("🚀 Testing Supervaizer Admin Interface")

    # Create basic agent methods (minimal demo implementation)
    basic_method = AgentMethod(
        name="Demo Method",
        method="demo.placeholder_method",  # This would be your actual method
        description="Demo method for admin interface testing",
    )

    # Create a simple agent for demo
    demo_agent = Agent(
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
    )

    # Create server with admin interface
    server = Server(
        agents=[demo_agent],
        host="127.0.0.1",
        port=8000,
        debug=True,
        api_key="test-admin-key-123",  # Enable admin interface
    )

    print(f"✅ Server created with {len(server.agents)} agent(s)")
    print("📊 Admin interface available at: http://127.0.0.1:8000/admin/")
    print("🔑 API Key: test-admin-key-123")
    print("📝 Add this header to access admin: X-API-Key: test-admin-key-123")
    print("\nStarting server...")

    # Start server
    server.launch()


if __name__ == "__main__":
    main()
