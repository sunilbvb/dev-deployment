import json
import os
from pathlib import Path
from typing import Any

from config import (
    add_app as config_add_app,
    check_system_health as config_check_system_health,
    discover_workspace_config,
    get_apps as config_get_apps,
    get_apps_config_file,
    get_commands_config_file,
    get_deploy_config_file,
    get_workspaces_list as config_get_workspaces_list,
    get_workspace_root as config_get_workspace_root,
    inspect_workspace_path as config_inspect_workspace_path,
    load_deploy_config,
    load_templates,
    save_deploy_config as config_save_deploy_config,
    scan_all_apps_config as config_scan_all_apps_config,
    scan_app_config as config_scan_app_config,
    set_active_workspace as config_set_active_workspace,
)
from commands import (
    _is_prod_store_deploy,
    get_commands as commands_get_commands,
    regenerate_commands as commands_regenerate_commands,
)
from p8 import upload_p8_key as p8_upload_p8_key
from jobs import (
    check_ios_expiry as jobs_check_ios_expiry,
    execute_command as jobs_execute_command,
    get_batch_deploy_plan as jobs_get_batch_deploy_plan,
    get_deployment_history as jobs_get_deployment_history,
    get_job as jobs_get_job,
    stop_job as jobs_stop_job,
)

# Pass-through bindings for backward compatibility
get_workspaces_list = config_get_workspaces_list
inspect_workspace_path = config_inspect_workspace_path
get_apps = config_get_apps
get_commands = commands_get_commands
load_deploy_config = load_deploy_config
load_templates = load_templates
scan_app_config = config_scan_app_config
check_ios_expiry = jobs_check_ios_expiry
get_job = jobs_get_job
get_deployment_history = jobs_get_deployment_history
get_batch_deploy_plan = jobs_get_batch_deploy_plan
execute_command = jobs_execute_command
stop_job = jobs_stop_job
save_deploy_config = config_save_deploy_config
regenerate_commands = commands_regenerate_commands
scan_all_apps_config = config_scan_all_apps_config
add_app = config_add_app
set_active_workspace = config_set_active_workspace
upload_p8_key = p8_upload_p8_key
check_system_health = config_check_system_health
get_workspace_root = config_get_workspace_root


