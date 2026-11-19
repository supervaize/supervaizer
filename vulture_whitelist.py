# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Vulture whitelist for supervaizer (`just vulture`).

Vulture scans only src/supervaizer, so it does not see Pydantic, FastAPI
and dynamic registration, or callers in agent code and tests. Supervaizer
is a public package: do not delete a public name because it is listed here.
Regenerate candidates with `uv run vulture --make-whitelist`.
"""

# False positives (258): framework fields, dynamic registration, test-only helpers
__getattr__  # __init__.py: PEP 562 lazy exports
supervaizer_VERSION  # account.py: model field / enum member
model_config  # account.py: model field / enum member
_._create_api_result  # account.py: used by tests
memory_usage_mb  # admin/routes.py: admin handler, registered with add_api_route
active_connections  # admin/routes.py: admin handler, registered with add_api_route
agents_count  # admin/routes.py: admin handler, registered with add_api_route
database_type  # admin/routes.py: admin handler, registered with add_api_route
storage_path  # admin/routes.py: admin handler, registered with add_api_route
database_type  # admin/routes.py: admin handler, registered with add_api_route
storage_path  # admin/routes.py: admin handler, registered with add_api_route
_.admin_dashboard  # admin/routes.py: admin handler, registered with add_api_route
_.admin_jobs_page  # admin/routes.py: admin handler, registered with add_api_route
_.admin_cases_page  # admin/routes.py: admin handler, registered with add_api_route
_.admin_server_page  # admin/routes.py: admin handler, registered with add_api_route
_.admin_agents_page  # admin/routes.py: admin handler, registered with add_api_route
_.serve_static  # admin/routes.py: admin handler, registered with add_api_route
_.admin_console_page  # admin/routes.py: admin handler, registered with add_api_route
_.get_stats  # admin/routes.py: admin handler, registered with add_api_route
_.get_server_status_api  # admin/routes.py: admin handler, registered with add_api_route
_.register_server_with_supervisor  # admin/routes.py: admin handler, registered with add_api_route
_.get_agents_api  # admin/routes.py: admin handler, registered with add_api_route
_.get_agent_details  # admin/routes.py: admin handler, registered with add_api_route
_.get_jobs_api  # admin/routes.py: admin handler, registered with add_api_route
_.get_job_details  # admin/routes.py: admin handler, registered with add_api_route
_.get_cases_api  # admin/routes.py: admin handler, registered with add_api_route
_.get_case_details  # admin/routes.py: admin handler, registered with add_api_route
_.update_job_status  # admin/routes.py: admin handler, registered with add_api_route
_.update_case_status  # admin/routes.py: admin handler, registered with add_api_route
_.delete_job  # admin/routes.py: admin handler, registered with add_api_route
_.delete_case  # admin/routes.py: admin handler, registered with add_api_route
_.get_recent_activity  # admin/routes.py: admin handler, registered with add_api_route
_.log_stream  # admin/routes.py: admin handler, registered with add_api_route
_.test_log  # admin/routes.py: admin handler, registered with add_api_route
_.test_loguru  # admin/routes.py: admin handler, registered with add_api_route
_.debug_queue  # admin/routes.py: admin handler, registered with add_api_route
_.execute_console_command  # admin/routes.py: admin handler, registered with add_api_route
INT  # agent.py: model field / enum member
BOOL  # agent.py: model field / enum member
CHOICE  # agent.py: model field / enum member
MULTICHOICE  # agent.py: model field / enum member
DATE  # agent.py: model field / enum member
DATETIME  # agent.py: model field / enum member
FLOAT  # agent.py: model field / enum member
EMAIL  # agent.py: model field / enum member
model_config  # agent.py: model field / enum member
model_config  # agent.py: model field / enum member
supervaizer_VERSION  # agent.py: model field / enum member
supervaize_instructions_template_path  # agent.py: model field / enum member
model_config  # agent.py: model field / enum member
api_path  # agent.py: model field / enum member
CHAT  # case.py: model field / enum member
TRIGGER  # case.py: model field / enum member
NOTIFICATION  # case.py: model field / enum member
STATUS_UPDATE  # case.py: model field / enum member
INTERMEDIARY_DELIVERY  # case.py: model field / enum member
HITL  # case.py: model field / enum member
DELIVERABLE  # case.py: model field / enum member
VALIDATION  # case.py: model field / enum member
DELIVERY  # case.py: model field / enum member
ERROR  # case.py: model field / enum member
WARNING  # case.py: model field / enum member
INFO  # case.py: model field / enum member
model_config  # case.py: model field / enum member
model_config  # case.py: model field / enum member
source_type  # context.py: model field / enum member
source_type  # context.py: model field / enum member
excerpt  # context.py: model field / enum member
score  # context.py: model field / enum member
citation  # context.py: model field / enum member
source_type  # context.py: model field / enum member
instructions  # context.py: model field / enum member
citations  # context.py: model field / enum member
model_config  # contracts.py: model field / enum member
SERVER_ONLINE  # contracts.py: model field / enum member
SERVER_DOWN  # contracts.py: model field / enum member
AGENT_WAKEUP  # contracts.py: model field / enum member
AGENT_ANOMALY  # contracts.py: model field / enum member
AGENT_SEND_ANOMALY  # contracts.py: model field / enum member
AGENT_PING  # contracts.py: model field / enum member
INTERMEDIARY  # contracts.py: model field / enum member
JOB_START  # contracts.py: model field / enum member
JOB_STATUS  # contracts.py: model field / enum member
JOB_RESULT  # contracts.py: model field / enum member
JOB_TIMEOUT  # contracts.py: model field / enum member
CASE_END  # contracts.py: model field / enum member
CASE_STATUS  # contracts.py: model field / enum member
CASE_RESULT  # contracts.py: model field / enum member
CASE_ERROR  # contracts.py: model field / enum member
editable  # contracts.py: model field / enum member
visible_on  # contracts.py: model field / enum member
related_resource  # contracts.py: model field / enum member
sensitive  # contracts.py: model field / enum member
controller_contract_version  # contracts.py: model field / enum member
api_base_path  # contracts.py: model field / enum member
api_path  # contracts.py: model field / enum member
controller_version  # contracts.py: model field / enum member
json_rpc  # contracts.py: model field / enum member
sse  # contracts.py: model field / enum member
push_notifications  # contracts.py: model field / enum member
inbound_tasks  # contracts.py: model field / enum member
outbound_delegation  # contracts.py: model field / enum member
transport  # contracts.py: model field / enum member
external_interop  # contracts.py: model field / enum member
renderer_surface  # contracts.py: model field / enum member
tagline  # contracts.py: model field / enum member
summary  # contracts.py: model field / enum member
example_goals  # contracts.py: model field / enum member
avatar_url  # contracts.py: model field / enum member
quantity  # contracts.py: model field / enum member
agent_cost_usd  # contracts.py: model field / enum member
occurred_at  # contracts.py: model field / enum member
dry_run  # contracts.py: model field / enum member
phases  # contracts.py: model field / enum member
checkpoint_url  # contracts.py: model field / enum member
supported_statuses  # contracts.py: model field / enum member
action_scopes  # contracts.py: model field / enum member
default_timeout_seconds  # contracts.py: model field / enum member
offline_start_policy  # contracts.py: model field / enum member
offline_running_policy  # contracts.py: model field / enum member
title_field  # contracts.py: model field / enum member
search_fields  # contracts.py: model field / enum member
value_field  # contracts.py: model field / enum member
label_field  # contracts.py: model field / enum member
model_config  # contracts.py: model field / enum member
in_  # contracts.py: model field / enum member
min_length  # contracts.py: model field / enum member
max_length  # contracts.py: model field / enum member
min_items  # contracts.py: model field / enum member
max_items  # contracts.py: model field / enum member
placeholder  # contracts.py: model field / enum member
options_source  # contracts.py: model field / enum member
depends_on  # contracts.py: model field / enum member
basis  # contracts.py: model field / enum member
confirmation_required  # contracts.py: model field / enum member
cost_estimate  # contracts.py: model field / enum member
options_source  # contracts.py: model field / enum member
placeholder  # contracts.py: model field / enum member
depends_on  # contracts.py: model field / enum member
submit  # contracts.py: model field / enum member
view  # contracts.py: model field / enum member
display  # contracts.py: model field / enum member
mounted_views  # contracts.py: model field / enum member
display  # contracts.py: model field / enum member
visualization  # contracts.py: model field / enum member
widgets  # contracts.py: model field / enum member
value_field  # contracts.py: model field / enum member
label_field  # contracts.py: model field / enum member
reference_label  # contracts.py: model field / enum member
reference_help  # contracts.py: model field / enum member
reference_placeholder  # contracts.py: model field / enum member
supervaizer_contract_version  # contracts.py: model field / enum member
versions  # contracts.py: model field / enum member
user_id  # contracts.py: model field / enum member
actor  # contracts.py: model field / enum member
draft_session_id  # contracts.py: model field / enum member
assigned_at  # contracts.py: model field / enum member
actor  # contracts.py: model field / enum member
draft_session_id  # contracts.py: model field / enum member
artifact_id  # contracts.py: model field / enum member
gaps  # contracts.py: model field / enum member
summary  # contracts.py: model field / enum member
dedupe_keys  # contracts.py: model field / enum member
stable_external_ids_required  # contracts.py: model field / enum member
strictly_idempotent_response  # contracts.py: model field / enum member
convergent  # contracts.py: model field / enum member
proposed_value  # contracts.py: model field / enum member
suggestions  # contracts.py: model field / enum member
expires_at  # contracts.py: model field / enum member
deletable  # contracts.py: model field / enum member
cost_incurred  # contracts.py: model field / enum member
job_state  # contracts.py: model field / enum member
replay_safety  # contracts.py: model field / enum member
setup_plan  # contracts.py: model field / enum member
draft  # contracts.py: model field / enum member
dry_run  # contracts.py: model field / enum member
document  # contracts.py: model field / enum member
external_id  # contracts.py: model field / enum member
media_type  # contracts.py: model field / enum member
placeholder  # contracts.py: model field / enum member
options_source  # contracts.py: model field / enum member
depends_on  # contracts.py: model field / enum member
reopenable  # contracts.py: model field / enum member
activity  # contracts.py: model field / enum member
external_id  # contracts.py: model field / enum member
awaiting  # contracts.py: model field / enum member
outputs  # contracts.py: model field / enum member
lane  # contracts.py: model field / enum member
external_id  # contracts.py: model field / enum member
external_ref  # contracts.py: model field / enum member
previous_job_id  # contracts.py: model field / enum member
target_type  # contracts.py: model field / enum member
external_ref  # contracts.py: model field / enum member
external_version  # contracts.py: model field / enum member
sync_cursor  # contracts.py: model field / enum member
observed_at  # contracts.py: model field / enum member
INTEGER  # data_resource.py: model field / enum member
BOOLEAN  # data_resource.py: model field / enum member
DATE  # data_resource.py: model field / enum member
DATETIME  # data_resource.py: model field / enum member
TEXT  # data_resource.py: model field / enum member
EMAIL  # data_resource.py: model field / enum member
URL  # data_resource.py: model field / enum member
CREATE_ONLY  # data_resource.py: model field / enum member
NEVER  # data_resource.py: model field / enum member
editable  # data_resource.py: model field / enum member
visible_on  # data_resource.py: model field / enum member
related_resource  # data_resource.py: model field / enum member
sensitive  # data_resource.py: model field / enum member
model_config  # data_resource.py: model field / enum member
CLOUD_RUN_AVAILABLE  # deploy/drivers/__init__.py: model field / enum member
CLOUD_RUN_AVAILABLE  # deploy/drivers/__init__.py: model field / enum member
AWS_APP_RUNNER_AVAILABLE  # deploy/drivers/__init__.py: model field / enum member
AWS_APP_RUNNER_AVAILABLE  # deploy/drivers/__init__.py: model field / enum member
DELETE  # deploy/drivers/base.py: model field / enum member
IMAGE  # deploy/drivers/base.py: model field / enum member
cost_estimate  # deploy/drivers/base.py: model field / enum member
total_cost_estimate  # deploy/drivers/base.py: model field / enum member
estimated_duration  # deploy/drivers/base.py: model field / enum member
target_port  # deploy/drivers/base.py: model field / enum member
error_details  # deploy/drivers/base.py: model field / enum member
TIMEOUT  # deploy/health.py: model field / enum member
ERROR  # deploy/health.py: model field / enum member
UNKNOWN  # deploy/health.py: model field / enum member
provider_data  # deploy/state.py: model field / enum member
supervaizer_VERSION  # event.py: model field / enum member
supervaizer_VERSION  # job.py: model field / enum member
model_config  # parameter.py: model field / enum member
model_config  # parameter.py: model field / enum member
jsonrpc  # protocol/a2a/controller.py: model field / enum member
jsonrpc  # protocol/a2a/controller.py: model field / enum member
supervaizer_VERSION  # server.py: model field / enum member
model_config  # server.py: model field / enum member
JOB_NOT_FOUND  # server_utils.py: model field / enum member
AGENT_NOT_FOUND  # server_utils.py: model field / enum member
INVALID_PARAMETERS  # server_utils.py: model field / enum member
LOGS  # telemetry.py: model field / enum member
METRICS  # telemetry.py: model field / enum member
EVENTS  # telemetry.py: model field / enum member
TRACES  # telemetry.py: model field / enum member
EXCEPTIONS  # telemetry.py: model field / enum member
DIAGNOSTICS  # telemetry.py: model field / enum member
CUSTOM  # telemetry.py: model field / enum member
SYSTEM  # telemetry.py: model field / enum member
APPLICATION  # telemetry.py: model field / enum member
USER_INTERACTION  # telemetry.py: model field / enum member
SECURITY  # telemetry.py: model field / enum member
BUSINESS  # telemetry.py: model field / enum member
ENVIRONMENT  # telemetry.py: model field / enum member
NETWORKING  # telemetry.py: model field / enum member
CUSTOM  # telemetry.py: model field / enum member
INFO  # telemetry.py: model field / enum member
WARNING  # telemetry.py: model field / enum member
ERROR  # telemetry.py: model field / enum member
CRITICAL  # telemetry.py: model field / enum member
supervaizer_VERSION  # telemetry.py: model field / enum member
sub  # workspace_authorization.py: model field / enum member
jti  # workspace_authorization.py: model field / enum member

# Public API (57): kept for agent developers
_.api_url_team  # account.py: public property
_.push_job_update  # account.py: public method
_.push_job_update_sync  # account.py: public method
_.request_job_refresh  # account.py: public method
_.request_job_refresh_sync  # account.py: public method
_.register_agent  # account.py: public method
_.register_agent_sync  # account.py: deprecation candidate: no caller in any Runwaize repo
_.send_telemetry  # account.py: public method
close_httpx_client  # account_service.py: public function
AgentCustomMethodParams  # agent.py: deprecation candidate: no caller in any Runwaize repo
_.custom_methods_names  # agent.py: public property
_.is_scheduled  # case.py: public property
_.make_update  # case.py: public method
_.patch_step_sync  # case.py: deprecation candidate: no caller in any Runwaize repo
_.request_human_input  # case.py: public method
_.receive_human_input_sync  # case.py: public method
_.cancel_scheduled_steps  # case.py: public method
_.start_sync  # case.py: public method
_.to_json  # common.py: public property
AGENT_REFRESH_EFFECT  # contracts.py: public variable
ServerRegistrationContract  # contracts.py: public class
DataResourceListResponse  # contracts.py: deprecation candidate: no caller in any Runwaize repo
V2_ACTION_CONTEXT_ASSIGN  # contracts.py: public variable
V2JobSyncResult  # contracts.py: public class
resolve_controller_endpoint  # contracts.py: public function
build_data_resource_context_headers  # contracts.py: public function
_.get_image_digest  # deploy/docker.py: public method
_.iam_client  # deploy/drivers/aws_app_runner.py: deprecation candidate: no caller in any Runwaize repo
_.validate_configuration  # deploy/drivers/base.py: public method
_.verify_health_async  # deploy/health.py: deprecation candidate: no caller in any Runwaize repo
_.verify_multiple_endpoints  # deploy/health.py: public method
_.get_health_summary  # deploy/health.py: public method
display_health_results  # deploy/health.py: public function
HELLO_WORLD_BILLING_CATALOG  # examples/hello_world_agent.py: public variable
_.remove_case_id  # job.py: public method
_.is_stopped  # lifecycle.py: public property
_.is_running  # lifecycle.py: public property
_.is_anomaly  # lifecycle.py: public property
_.get_valid_transitions  # lifecycle.py: public method
_.generate_valid_transitions_dict  # lifecycle.py: public method
_.generate_mermaid_diagram  # lifecycle.py: public method
_.mermaid_diagram_all_steps  # lifecycle.py: public method
JobTransitions  # lifecycle.py: public variable
public_router  # routers/public.py: deprecation candidate: no caller in any Runwaize repo
_.from_job_start  # rule_controls.py: public method
recover_guarded_step  # rule_controls.py: public function
insp  # server.py: deprecation candidate: no caller in any Runwaize repo
_.instructions  # server.py: public method
_.reset_storage  # storage.py: public method
_.get_by_id  # storage.py: public method
_.save  # storage.py: public method
_.get_all  # storage.py: public method
_.delete  # storage.py: public method
create_job_repository  # storage.py: public function
create_case_repository  # storage.py: public function
assert_confirm_idempotent  # testing.py: public function
workspace_authorization_enabled  # workspace_authorization.py: deprecation candidate: no caller in any Runwaize repo
