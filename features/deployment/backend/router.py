import adb_manager
import artifacts
import build_profiler
import build_size
import cache_warmer
import credentials
import docs_provider
import doctor
import github_actions
import notifications
import picker
import pipelines
import qr
import sentinel
import server_manager
from config import (
    add_app as config_add_app,
    allow_workspace as config_allow_workspace,
    remove_workspace as config_remove_workspace,
    check_system_health as config_check_system_health,
    get_apps as config_get_apps,
    get_workspaces_list as config_get_workspaces_list,
    get_workspace_root as config_get_workspace_root,
    inspect_workspace_path as config_inspect_workspace_path,
    load_deploy_config,
    load_templates,
    rescan_workspace as config_rescan_workspace,
    save_deploy_config as config_save_deploy_config,
    scan_all_apps_config as config_scan_all_apps_config,
    scan_app_config as config_scan_app_config,
    set_active_workspace as config_set_active_workspace,
)
from commands import (
    get_commands as commands_get_commands,
    regenerate_commands as commands_regenerate_commands,
)
from p8 import upload_p8_key as p8_upload_p8_key
from jobs import (
    check_ios_expiry as jobs_check_ios_expiry,
    execute_command as jobs_execute_command,
    get_deployment_history as jobs_get_deployment_history,
    get_job as jobs_get_job,
    get_running_jobs as jobs_get_running_jobs,
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
get_running_jobs = jobs_get_running_jobs
get_deployment_history = jobs_get_deployment_history
execute_command = jobs_execute_command
stop_job = jobs_stop_job
save_deploy_config = config_save_deploy_config
regenerate_commands = commands_regenerate_commands
scan_all_apps_config = config_scan_all_apps_config
add_app = config_add_app
set_active_workspace = config_set_active_workspace
upload_p8_key = p8_upload_p8_key
scan_credentials = credentials.scan_credentials
import_credential_path = credentials.import_credential_path
import_credential_bytes = credentials.import_credential_bytes
remove_credential = credentials.remove_credential
get_credentials_status = credentials.get_credentials_status
pick_path = picker.pick_path
check_system_health = config_check_system_health
get_workspace_root = config_get_workspace_root
rescan_workspace = config_rescan_workspace
allow_workspace = config_allow_workspace
remove_workspace = config_remove_workspace
get_pipelines = pipelines.get_pipelines
resolve_pipeline = pipelines.resolve_pipeline
save_pipeline = pipelines.save_pipeline
delete_pipeline = pipelines.delete_pipeline
run_pipeline = pipelines.run_pipeline
stop_pipeline_run = pipelines.stop_pipeline_run
get_pipeline_run = pipelines.get_pipeline_run
diagnose_app = doctor.diagnose_app
get_apk_download_info = artifacts.get_apk_download_info
resolve_safe_apk_path = artifacts.resolve_safe_apk_path
find_apk_artifact = artifacts.find_apk_artifact
get_ipa_download_info = artifacts.get_ipa_download_info
resolve_safe_ipa_path = artifacts.resolve_safe_ipa_path
find_ipa_artifact = artifacts.find_ipa_artifact
generate_ota_manifest_plist = artifacts.generate_ota_manifest_plist
get_lan_ip = artifacts.get_lan_ip
qr_svg = qr.qr_svg
qr_ascii = qr.qr_ascii
generate_qr = qr.generate_qr
generate_qr_matrix = qr.generate_qr_matrix
test_webhook = notifications.test_webhook
detect_webhook_provider = notifications.detect_webhook_provider
send_outgoing_webhook = notifications.send_outgoing_webhook
notify_job_finished = notifications.notify_job_finished
notify_pipeline_finished = notifications.notify_pipeline_finished
get_webhook_config_for_app = notifications.get_webhook_config_for_app
get_webhook_channels_for_app = notifications.get_webhook_channels_for_app
check_app_sentinel = sentinel.check_app_sentinel
check_workspace_sentinel = sentinel.check_workspace_sentinel
check_apple_expiry = sentinel.check_apple_expiry
check_android_keystore_expiry = sentinel.check_android_keystore_expiry
check_firebase_mismatch = sentinel.check_firebase_mismatch
find_build_artifact = build_size.find_build_artifact
inspect_archive_contents = build_size.inspect_archive_contents
compare_build_size = build_size.compare_build_size
inspect_and_diff_job = build_size.inspect_and_diff_job
get_build_size_info = build_size.get_build_size_info
get_adb_devices = adb_manager.get_adb_devices
connect_wireless_adb = adb_manager.connect_wireless_adb
disconnect_wireless_adb = adb_manager.disconnect_wireless_adb
push_apk_to_devices = adb_manager.push_apk_to_devices
get_job_build_profile = build_profiler.get_job_build_profile
get_cache_warmer_status = cache_warmer.get_cache_warmer_status
trigger_cache_warm = cache_warmer.trigger_cache_warm
start_cache_warmer_daemon = cache_warmer.start_cache_warmer_daemon
stop_cache_warmer_daemon = cache_warmer.stop_cache_warmer_daemon

get_doc_content = docs_provider.get_doc_content
list_available_docs = docs_provider.list_available_docs
get_server_status_info = docs_provider.get_server_status_info
install_desktop_launcher = server_manager.install_desktop_launcher
install_systemd_service = server_manager.install_systemd_service
get_service_status = server_manager.get_service_status


def get_github_status(app_id: str = "") -> dict:
    ws_root = get_workspace_root()
    repo = github_actions.detect_github_repo(ws_root)
    branch = github_actions.detect_git_branch(ws_root)
    token = github_actions.get_stored_github_token()
    wf_file = github_actions.find_workflow_file(ws_root)
    wf_exists = (ws_root / ".github" / "workflows" / wf_file).exists()
    return {
        "success": True,
        "repo": repo,
        "branch": branch,
        "tokenConfigured": bool(token),
        "tokenMasked": (token[:4] + "..." + token[-4:]) if token and len(token) > 8 else ("configured" if token else None),
        "workflowFile": wf_file,
        "workflowExists": wf_exists,
    }


def save_github_config(token: str | None = None, repo: str | None = None) -> dict:
    if token is not None:
        github_actions.save_github_token(token)
    if repo is not None:
        github_actions.save_repo_override(repo)
    return {"success": True, "message": "GitHub configuration saved."}


def get_github_workflow_template() -> dict:
    return {"success": True, "template": github_actions.get_android_workflow_template()}


def install_github_workflow() -> dict:
    ok, msg = github_actions.install_workflow_template(get_workspace_root())
    return {"success": ok, "message": msg}


def dispatch_github_workflow(app: str, flavor: str = "prod", build_type: str = "apk", ref: str = "") -> dict:
    cmd = f"github-actions build {build_type} --flavor {flavor}"
    template_id = f"build_{build_type}"
    return execute_command(
        app=app,
        command=cmd,
        runner="github_actions",
        flavor=flavor,
        template_id=template_id,
        env=flavor,
        confirmed=True,
    )


