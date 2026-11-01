import http.client
import http.server
import json
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Add backend and tests directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features" / "deployment" / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import deploy_queue
from deploy_queue.engine import (
    _reset_queue_state_for_testing,
    add_to_queue,
    clear_queue,
    get_queue_status,
    pause_queue,
    remove_from_queue,
    reorder_queue,
    retry_queue_item,
)
import router
import server
from _isolation import isolate_dashboard_config, restore_dashboard_config


def setUpModule():
    isolate_dashboard_config()


def tearDownModule():
    restore_dashboard_config()


class TestDeploymentQueue(unittest.TestCase):

    def setUp(self):
        _reset_queue_state_for_testing()

    def tearDown(self):
        _reset_queue_state_for_testing()

    def test_router_exports(self):
        self.assertTrue(callable(router.get_queue_status))
        self.assertTrue(callable(router.add_to_queue))
        self.assertTrue(callable(router.remove_from_queue))
        self.assertTrue(callable(router.reorder_queue))
        self.assertTrue(callable(router.clear_queue))
        self.assertTrue(callable(router.pause_queue))
        self.assertTrue(callable(router.resume_queue))
        self.assertTrue(callable(router.stop_current_queue_item))
        self.assertTrue(callable(router.retry_queue_item))

    def test_initial_queue_status(self):
        st = get_queue_status()
        self.assertTrue(st["success"])
        self.assertEqual(len(st["queue"]), 0)
        self.assertIsNone(st["activeItem"])
        self.assertFalse(st["isPaused"])
        self.assertEqual(st["counts"]["total"], 0)

    def test_add_to_queue_invalid_app(self):
        res = add_to_queue(app="../bad_app!", command="build_apk")
        self.assertFalse(res["success"])
        self.assertIn("Invalid app ID", res["error"])

    @patch("commands.get_commands")
    def test_add_and_remove_from_queue(self, mock_cmds):
        mock_cmds.return_value = {
            "commands": [
                {"key": "build_apk", "templateId": "build_apk", "flavor": "prod", "title": "Build APK"}
            ]
        }
        pause_queue()  # Pause to avoid background execution
        res = add_to_queue(app="test_app", command="build_apk", template_id="build_apk", flavor="prod")
        self.assertTrue(res["success"])
        item = res["item"]
        self.assertEqual(item["app"], "test_app")
        self.assertEqual(item["status"], "pending")
        self.assertEqual(item["flavor"], "prod")

        st = get_queue_status()
        self.assertEqual(len(st["queue"]), 1)
        self.assertEqual(st["counts"]["pending"], 1)

        # Remove item
        rem_res = remove_from_queue(item["id"])
        self.assertTrue(rem_res["success"])
        st_after = get_queue_status()
        self.assertEqual(len(st_after["queue"]), 0)

    @patch("commands.get_commands")
    def test_reorder_queue(self, mock_cmds):
        mock_cmds.return_value = {
            "commands": [
                {"key": "build_apk", "templateId": "build_apk", "flavor": "prod", "title": "Build APK"},
                {"key": "build_aab", "templateId": "build_aab", "flavor": "prod", "title": "Build AAB"},
            ]
        }
        pause_queue()

        res1 = add_to_queue(app="app_a", command="build_apk", template_id="build_apk")
        res2 = add_to_queue(app="app_b", command="build_aab", template_id="build_aab")
        id1 = res1["item"]["id"]
        id2 = res2["item"]["id"]

        st = get_queue_status()
        self.assertEqual([i["id"] for i in st["queue"]], [id1, id2])

        # Reverse order
        reorder_res = reorder_queue([id2, id1])
        self.assertTrue(reorder_res["success"])
        st2 = get_queue_status()
        self.assertEqual([i["id"] for i in st2["queue"]], [id2, id1])

    @patch("commands.get_commands")
    def test_clear_queue(self, mock_cmds):
        mock_cmds.return_value = {
            "commands": [
                {"key": "build_apk", "templateId": "build_apk", "flavor": "prod", "title": "Build APK"}
            ]
        }
        pause_queue()
        add_to_queue(app="app_a", command="build_apk", template_id="build_apk")
        add_to_queue(app="app_b", command="build_apk", template_id="build_apk")

        self.assertEqual(get_queue_status()["counts"]["pending"], 2)
        clr = clear_queue(clear_all=False)
        self.assertTrue(clr["success"])
        self.assertEqual(get_queue_status()["counts"]["pending"], 0)

    @patch("commands.get_commands")
    @patch("jobs.get_job")
    @patch("jobs.execute_command")
    def test_sequential_execution(self, mock_exec, mock_get_job, mock_cmds):
        mock_cmds.return_value = {
            "commands": [
                {"key": "build_apk", "templateId": "build_apk", "flavor": "prod", "title": "Build APK"}
            ]
        }
        mock_exec.return_value = {"success": True, "jobId": "job_123", "command": "build_apk"}
        mock_get_job.return_value = {"status": "success", "return_code": 0}

        # Add item while unpaused
        res = add_to_queue(app="app_a", command="build_apk", template_id="build_apk")
        self.assertTrue(res["success"])

        # Wait for worker thread to complete
        import time
        for _ in range(20):
            time.sleep(0.1)
            st = get_queue_status()
            if st["counts"]["completed"] >= 1:
                break

        final_st = get_queue_status()
        self.assertEqual(final_st["counts"]["completed"], 1)
        self.assertEqual(final_st["counts"]["pending"], 0)
        self.assertIsNone(final_st["activeItem"])

    @patch("commands.get_commands")
    def test_retry_failed_item(self, mock_cmds):
        mock_cmds.return_value = {
            "commands": [
                {"key": "build_apk", "templateId": "build_apk", "flavor": "prod", "title": "Build APK"}
            ]
        }
        pause_queue()
        res = add_to_queue(app="app_a", command="build_apk", template_id="build_apk")
        item_id = res["item"]["id"]

        # Simulate failure
        with deploy_queue.engine._QUEUE_LOCK:
            deploy_queue.engine._QUEUE_ITEMS[0]["status"] = "failed"
            deploy_queue.engine._QUEUE_ITEMS[0]["error"] = "Gradle syntax error"

        self.assertEqual(get_queue_status()["counts"]["failed"], 1)

        # Retry item
        retry_res = retry_queue_item(item_id)
        self.assertTrue(retry_res["success"])
        st = get_queue_status()
        self.assertEqual(st["counts"]["pending"], 1)
        self.assertEqual(st["counts"]["failed"], 0)

    @patch("commands.get_commands")
    def test_multi_workspace_queue(self, mock_cmds):
        from config import set_request_workspace, reset_request_workspace
        mock_cmds.return_value = {
            "commands": [
                {"key": "build_apk", "templateId": "build_apk", "flavor": "prod", "title": "Build APK"}
            ]
        }
        pause_queue()

        ws1 = Path("/tmp/mock_ws_1")
        ws2 = Path("/tmp/mock_ws_2")

        t1 = set_request_workspace(ws1)
        try:
            res1 = add_to_queue(app="app_ws1", command="build_apk", template_id="build_apk")
            self.assertTrue(res1["success"])
            self.assertEqual(res1["item"]["workspace"], str(ws1.resolve()))
        finally:
            reset_request_workspace(t1)

        t2 = set_request_workspace(ws2)
        try:
            res2 = add_to_queue(app="app_ws2", command="build_apk", template_id="build_apk")
            self.assertTrue(res2["success"])
            self.assertEqual(res2["item"]["workspace"], str(ws2.resolve()))
        finally:
            reset_request_workspace(t2)

        st = get_queue_status()
        self.assertEqual(len(st["queue"]), 2)
        self.assertEqual(st["queue"][0]["workspace"], str(ws1.resolve()))
        self.assertEqual(st["queue"][1]["workspace"], str(ws2.resolve()))


class TestQueueServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _reset_queue_state_for_testing()
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=1.0)
        _reset_queue_state_for_testing()

    def setUp(self):
        _reset_queue_state_for_testing()

    def _headers(self):
        token = server._get_auth_token()
        return {"X-API-Token": token, "Content-Type": "application/json"}

    def test_queue_http_endpoints(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        # GET /api/deployment/queue
        conn.request("GET", "/api/deployment/queue", headers=self._headers())
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode())
        self.assertTrue(data["success"])
        self.assertEqual(len(data["queue"]), 0)

        # POST /api/deployment/queue/pause
        conn.request("POST", "/api/deployment/queue/pause", body=json.dumps({}), headers=self._headers())
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        p_data = json.loads(res.read().decode())
        self.assertTrue(p_data["isPaused"])

        # POST /api/deployment/queue/resume
        conn.request("POST", "/api/deployment/queue/resume", body=json.dumps({}), headers=self._headers())
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        r_data = json.loads(res.read().decode())
        self.assertFalse(r_data["isPaused"])


if __name__ == "__main__":
    unittest.main()
