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

GET_AGENT_BY_SUCCESS_RESPONSE_DETAIL = {
    "id": "LMKyPAS2Q8sKWBY34DS37a",
    "name": "competitor_summary",
    "status": "active",
    "onboarding_status": "configured",
    "created_at": "2025-04-05T08:46:28.505543Z",
    "updated_at": "2025-04-05T15:00:55.589209Z",
    "created_by": None,
    "updated_by": None,
    "tags": [],
    "deployment_config": {
        "author": "John Doe",
        "version": "1.2",
        "developer": "Develop",
        "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA3AGPoPHvqQWd4kDGHe+d\nbtRMj+BhwkIMFK1jM8uokNEpKxkYyPogOlJfLPxlukX0Mag6t+8IDZeCTKnLSjN6\nSAjJNIxi2ab4D805nB9UESd1IRAXJS9CHEr5G5pSixB pRrCPRUJLJK590Me3H9iY\n3xYeewaOFDP5DxnoHSCINhmJPGaj0fhmNh0Spf1CWK5vVRmFfAg7N2Dg1/3NO2qE\nD7RrpySz3TUcixS6yxADR2sOCTPtgudLaWgsJtBx/1tNIPI6MSpxuULk5IyTiZmn\ncW/2vKslicTB04I4hd7iEqkZn8Eyex dWfhswjUrk+3arGmsCkQaO4UnrSUll8fHp\nlwIDAQAB\n-----END PUBLIC KEY-----\n",
        "server_uri": "server:E2-AC-ED-22-BF-B4",
        "server_url": "http://0.0.0.0:8001",
        "environment": "dev",
    },
    "parameters_setup": [
        {
            "id": "01JR2KB47RGSCJMGZEKC4WDS3G",
            "name": "OPEN_API_KEY",
            "description": "OpenAPI Key",
            "is_environment": True,
        },
        {
            "id": "01JR2KB47T91AVXB0DMDVCQHP7",
            "name": "SERPER_API",
            "description": "Server API key updated",
            "is_environment": True,
        },
        {
            "id": "01JR2KB47W196N6DV7X06QAH40",
            "name": "COMPETITOR_SUMMARY_URL",
            "description": "Competitor Summary URL",
            "is_environment": True,
        },
    ],
    "parameters_encrypted": "xbakqBa9X70m2aeLV8WQH7L2qWuB439FBUUryXTUpo5NcgkGLAv5M8dToZqAwo0bzEGYMb6Onw6RGvYFDxE1zlewOx3mPfs42OA1QmeIEvyUspDs2xspUrKFH12ScD0XWxMtxH+6w93IE9nlV2OjXchtPC0EOOWs8woDqHFgkZJIyEzClJ+uDTge QiGlRi0y8tTQayBvWe0HhRFkoo20MrvAFfpmadMWPT2ixpj/sr2wEidj7a58FP1M8iDEq095egvgBahvalfYjFutG6bieRDix089XTWOuOPcKNPFuQoAufguy2mc1gXOcoydR8Lwf4SO+7KxEp/ApRL3Vm2l8NCj9dRF9LoXIutPbhOv8A4OX7sty KNgkAZbvJP/BJ9+b8ZLcKyoTV8dThHL2sOgmNzmXOIeb/iTFhGIu3GuLPNLVRaYhDyDbXFo+Dv5WuPJPEgxMKgjdaWcKlsZUObllBWVL+R67t9H/EOTv1aWAnJD1m6l1109DXoDIsOeiISuAttdnX9OzZoMl6FIwcHPOBc3/DHF7WDZ6o3LXJ6Pgk Xa0sMwaDiYfGOdf8p1Np/PdwTn399OdkkIphDgEXr5mtxl81FWEQPpENC9V5JROLICDeqPrjUsXktVW5sz4cyrsWZfLVtCC+6w1/d5OJ54EaFyih38FUaRoD8vrgKCO/XDRoJErfHc8XQNb31C6X7xFulcsGsrSWmI23wn1SWlK4797eK9SkQRVRs /satk2qfpwpt32/GaNFbXtDKOvMzvd7kHHaSf8MlpARBShu4JP6VLwp8mSfKpB0eUQmb1wFam/DOfNg8UZQajPczeVIf5MWeV1wAHYiIm/cDNmAA+IAIpi+0WCyl0ahaoat2tUW2AQ9YbMuh9sg389ffMgD15",
}
