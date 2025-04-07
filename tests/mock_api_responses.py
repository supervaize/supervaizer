# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


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


EVENT_REGISTER_SERVER_PAYLOAD = {
    "name": "server.register server:E2-AC-ED-22-BF-B1",
    "source": "server:E2-AC-ED-22-BF-B1",
    "account": "o34Z484gY9Nxz8axgTAdiH",
    "event_type": "server.register",
    "details": {
        "url": "http://0.0.0.0:8001",
        "uri": "server:E2-AC-ED-22-BF-B1",
        "api_version": "v1",
        "environment": "dev",
        "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAv6uXhCfhzXHYGmJOmhHE\nbWE+j79/l/IJ9tQ/ADJXUUbi7F81/94Jl8o0jH9Qn1+t2462Ajk7q6koIBUJH5kT\nPkCCdScpiL58c6l3NRMy2hYuILxWDIjsfkHF/eimCYubXjnm3u4VmDaRwB8kaNdM\nHqWSH7Vz4/mR3qI54cHJp3KWLDJ+pmcbTpIDguF2yfRfZk8vYaXM+M32Fk10IgFL\nuGU9UgjzA1AGSkc2mBqNa6sXbk93RHWDNLXr0ghRvb1gIo/IVmpOaPqkiihTzOQ2\nkNPzpkC6do8AQMBmlYLkJdyOYSoeu6C7z6Kwb1aMFDoXuOPW80ZkIv6cahSlTiIv\nQwIDAQAB\n-----END PUBLIC KEY-----\n",
        "docs": {
            "swagger": "http://0.0.0.0:8001/docs",
            "redoc": "http://0.0.0.0:8001/redoc",
            "openapi": "http://0.0.0.0:8001/openapi.json",
        },
        "agents": [
            {
                "name": "competitor_summary",
                "id": "bwNtj65WC3SYoEGN6rpAWU",
                "author": "John Doe",
                "developer": "Develop",
                "version": "1.2",
                "description": "This is a test agent",
                "path": "/agents/competitor-summary",
                "tags": ["testtag", "testtag2"],
                "job_start_method": {
                    "name": "start",
                    "method": "control.example_synchronous_job_start",
                    "params": {"action": "start"},
                    "fields": [
                        {
                            "name": "full_name",
                            "field_type": "CharField",
                            "max_length": 100,
                            "required": True,
                        },
                        {"name": "age", "field_type": "IntegerField", "required": True},
                        {
                            "name": "subscribe",
                            "field_type": "BooleanField",
                            "required": False,
                        },
                        {
                            "name": "gender",
                            "field_type": "ChoiceField",
                            "choices": [["M", "Male"], ["F", "Female"]],
                            "widget": "RadioSelect",
                            "required": True,
                        },
                        {
                            "name": "bio",
                            "field_type": "CharField",
                            "widget": "Textarea",
                            "required": False,
                        },
                        {
                            "name": "country",
                            "field_type": "ChoiceField",
                            "choices": [["US", "United States"], ["CA", "Canada"]],
                            "required": True,
                        },
                        {
                            "name": "languages",
                            "field_type": "MultipleChoiceField",
                            "choices": [
                                ["en", "English"],
                                ["fr", "French"],
                                ["es", "Spanish"],
                            ],
                            "required": False,
                        },
                    ],
                    "description": "Start the collection of new competitor summary",
                },
                "job_stop_method": {
                    "name": "stop",
                    "method": "control.stop",
                    "params": {"action": "stop"},
                    "fields": [],
                    "description": "Stop the agent",
                },
                "job_status_method": {
                    "name": "status",
                    "method": "hello.mystatus",
                    "params": {"status": "statusvalue"},
                    "fields": [],
                    "description": "Get the status of the agent",
                },
                "chat_method": None,
                "custom_methods": {
                    "custom1": {
                        "name": "custom",
                        "method": "control.custom",
                        "params": {"action": "custom"},
                        "fields": [],
                        "description": "Custom method",
                    }
                },
                "parameters_setup": [
                    {
                        "name": "OPEN_API_KEY",
                        "description": "OpenAPI Key",
                        "is_environment": True,
                    },
                    {
                        "name": "SERPER_API",
                        "description": "Server API key updated",
                        "is_environment": True,
                    },
                    {
                        "name": "COMPETITOR_SUMMARY_URL",
                        "description": "Competitor Summary URL",
                        "is_environment": True,
                    },
                ],
                "server_agent_id": None,
                "server_agent_status": None,
                "server_agent_onboarding_status": None,
                "server_encrypted_parameters": None,
            }
        ],
    },
}


JOB_START_PARAMS_EXAMPLE = {
    "supervaize_context": {
        "workspace_id": "string",
        "job_id": "string",
        "started_by": "string",
        "started_at": "2025-04-07T16:35:10.652Z",
        "mission_id": "string",
        "mission_name": "string",
        "mission_context": "string",
        "job_conditions": {
            "max_cases": 0,
            "max_duration": 0,
            "max_cost": 0,
            "stop_on_warning": False,
            "stop_on_error": True,
        },
    },
    "job_fields": {
        "full_name": "string",
        "age": 0,
        "subscribe": True,
        "gender": "string",
        "bio": "string",
        "country": "string",
        "languages": ["string"],
    },
}
