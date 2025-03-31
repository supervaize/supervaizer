# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Those are the responses expected from the Supervaize API.i

AGENT_METHOD_EXAMPLE = {
    "name": "start",
    "method": "start",
    "params": {"param1": "value1"},
    "fields": [],
    "description": "Start the agent",
}

AGENT_INFO_EXAMPLE = {
    "name": "agentName",
    "id": "LMKyPAS2Q8sKWBY34DS37a",
    "author": "authorName",
    "developer": "Dev",
    "version": "1.0.0",
    "description": "description",
    "tags": None,
    "uri": "agent:LMKyPAS2Q8sKWBY34DS37a",
    "slug": "agentname",
    "job_start_method": AGENT_METHOD_EXAMPLE,
    "job_stop_method": AGENT_METHOD_EXAMPLE,
    "job_status_method": AGENT_METHOD_EXAMPLE,
    "chat_method": AGENT_METHOD_EXAMPLE,
    "custom_methods": {
        "method1": AGENT_METHOD_EXAMPLE,
        "method2": AGENT_METHOD_EXAMPLE,
    },
    "parameters_setup": {
        "parameters": [
            {
                "name": "param1",
                "description": "description",
                "is_secret": False,
            }
        ]
    },
    "agent_parameters_encrypted": "encrypted_parameters",
}

WAKEUP_EVENT_RESPONSE = {
    "id": "01JPZ430YYATCVK48ADMSC8QDV",
    "name": "agent.wakeup test",
    "source": "test",
    "account": "o34Z484gY9Nxz8axgTAdiH",
    "event_type": "agent.wakeup",
    "details": {"test": "value"},
    "created_at": "2025-03-22T14:28:39.519242Z",
    "updated_at": "2025-03-22T14:28:39.519254Z",
    "created_by": 1,
    "updated_by": 1,
}

SERVER_REGISTER_RESPONSE = {
    "id": "01JPZ7414FX3JHPNA8N1JXDADX",
    "name": "server.send.registration server:E2-AC-ED-22-BF-B1",
    "source": "server:E2-AC-ED-22-BF-B1",
    "account": "o34Z484gY9Nxz8axgTAdiH",
    "event_type": "server.register",
    "details": {
        "url": "http://localhost:8001",
        "uri": "server:E2-AC-ED-22-BF-B1",
        "environment": "test",
        "agents": [AGENT_INFO_EXAMPLE],
    },
    "created_at": "2025-03-22T15:21:38.191669Z",
    "updated_at": "2025-03-22T15:21:38.191675Z",
    "created_by": 1,
    "updated_by": 1,
}
SERVER_REGISTER_RESPONSE_NO_AGENTS_ERROR = {
    "details": {
        "url": "http://localhost:8001",
        "uri": "server:E2-AC-ED-22-BF-B1",
        "environment": "test",
    },
}
SERVER_REGISTER_RESPONSE_UNKNOWN_AGENTS_ERROR = {
    "details": {
        "url": "http://localhost:8001",
        "uri": "server:E2-AC-ED-22-BF-B1",
        "environment": "test",
        "agents": [{"name": "unknown_agent"}],
    }
}
SERVER_REGISTER_RESPONSE_UNKNOWN_AND_UNKNOWN_AGENTS_ERROR = {
    "details": {
        "url": "http://localhost:8001",
        "uri": "server:E2-AC-ED-22-BF-B1",
        "environment": "test",
        "agents": [
            {"name": "unknown_agent"},
            AGENT_INFO_EXAMPLE,
        ],
    }
}


AUTH_ERROR_RESPONSE = {"detail": "Authentication credentials were not provided."}
