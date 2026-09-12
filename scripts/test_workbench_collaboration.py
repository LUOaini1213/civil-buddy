"""End-to-end task routing, parallel tender work and scoped context via HTTP."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
import json
import os
import sys
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "demo")]
from scripts import test_workbench_flow as flow
import context
import projects
import uploads
import llm as demo_llm
import turn_control
from scripts.test_workbench_cancel import BlockedModel

TENDER = """一、投标人须具备建筑工程施工资质。
二、未实质性响应作废标。
三、交货期90个日历天。
四、技术标评分：施工组织设计25分、项目管理机构10分。
五、★深基坑专项方案须编制。
"""
RESPONSE = "投标人须具备建筑工程施工资质。营业执照扫描件尚缺。"


class CollaborationFlowTests(unittest.TestCase):
    post = flow.WorkbenchFlowTests.post

    def setUp(self):
        flow.WorkbenchFlowTests.setUp(self)
        context.set_runtime_policy(None)
        self.addCleanup(context.set_runtime_policy, None)

    def seed_attachments(self):
        tender = uploads.save_upload(self.sid, "招标文件.txt", TENDER.encode())
        response = uploads.save_upload(self.sid, "响应文件.txt", RESPONSE.encode())
        return tender, response

    def test_simple_task_routes_and_runs_without_collaboration(self):
        done, events = self.post("整理日报，日期：2031年5月6日，部位：东桥。")
        self.assertEqual(done["skill"], "pm-daily")
        self.assertTrue(done["wrote"], done)
        self.assertIsNone(done["collaboration"])
        self.assertTrue(any(event["data"].get("phase") == "routing" for event in events))

    def test_ambiguous_request_returns_candidates_without_writes_or_model(self):
        done, _ = self.post("整理设计变更")
        self.assertTrue(done["route"]["ambiguous"])
        self.assertEqual({c["expert_ids"][0] for c in done["route"]["candidates"]}, {"variation", "design-coord"})
        self.assertFalse(done["wrote"])

    def test_collaboration_runs_real_tools_and_restores_sources_and_roles(self):
        tender, response = self.seed_attachments()
        roles = {tender["id"]: "tender", response["id"]: "response"}
        done, events = self.post("全面检查投标响应并汇总缺项。", attachments=list(roles), attachment_roles=roles)
        self.assertTrue(done["ok"], done)
        self.assertTrue(done["wrote"])
        self.assertFalse(done["hitl_pending"])
        self.assertTrue(done["submit_blocked"])
        value = done["collaboration"]
        self.assertEqual({c["skill"] for c in value["children"]}, {"bid-tech", "bid-compliance"})
        self.assertTrue(all(c["status"] == "done" for c in value["children"]))
        self.assertTrue(value["review"]["handoff_unchanged"])
        self.assertTrue(value["review"]["response_evidence_supplied"])
        self.assertEqual(value["aggregate_metrics"]["model_calls"], 0)
        self.assertLessEqual(value["aggregate_metrics"]["reserved_tokens"], value["aggregate_metrics"]["limit"])
        for child in value["children"]:
            for evidence in child["evidence"]:
                if "quote" in evidence:
                    self.assertTrue(evidence["quote"] in TENDER or evidence["quote"] in RESPONSE)
        for file in done["deliverables"]:
            self.assertTrue(Path(file["path"]).is_file(), file)
        self.assertTrue(any(e["event"] == "collaboration" for e in events))
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(restored["attachment_roles"], roles)
        self.assertEqual(restored["collaboration"]["parent_run_id"], value["parent_run_id"])
        status = self.client.get(f"/api/workflows/{self.sid}/{value['parent_run_id']}")
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json()["active"])
        foreign = self.client.get(f"/api/workflows/foreign-task/{value['parent_run_id']}")
        self.assertEqual(foreign.status_code, 404)

    def test_selected_single_post_does_not_expand_into_workflow(self):
        done, _ = self.post("全面检查投标响应并汇总缺项。", expert_ids=["bid-compliance"])
        self.assertEqual(done["skill"], "bid-compliance")
        self.assertIsNone(done["collaboration"])

    def test_untrusted_workflow_waits_for_current_confirmation(self):
        tender, response = self.seed_attachments()
        with patch.dict(os.environ, {"CIVIL_APPROVAL": "untrusted"}):
            waiting, _ = self.post("全面检查投标响应并汇总缺项。", attachments=[tender["id"], response["id"]])
            self.assertTrue(waiting["hitl_pending"])
            self.assertFalse(waiting["wrote"])
            self.assertEqual(waiting["collaboration"]["state"], "waiting_hitl")
            self.assertFalse(list((self.root / self.sid / "workflows").glob("*/workflow.json")))
            allowed, _ = self.post("全面检查投标响应并汇总缺项。", attachments=[tender["id"], response["id"]], confirm_ok=True)
        self.assertTrue(allowed["ok"] and allowed["wrote"], allowed)
        self.assertFalse(allowed["hitl_pending"])
        self.assertTrue(allowed["submit_blocked"])

    def test_question_never_starts_business_workflow(self):
        done, _ = self.post("解释一下全面检查投标响应需要哪些资料？")
        self.assertEqual(done["intent"], "chat")
        self.assertFalse(done["wrote"])
        self.assertIsNone(done["collaboration"])

    def test_invalid_roles_and_budget_are_rejected_before_stream(self):
        for extra in ({"attachment_roles": {"unselected": "tender"}},
                      {"workflow_budget": {"total_tokens": True}},
                      {"workflow_budget": {"worker_tokens": 100000}}):
            response = self.client.post("/api/chat", json={"session_id": self.sid,
                "message": "全面检查投标响应", **extra})
            self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(projects.read_full_history(self.root, self.sid), [])

    def test_configured_model_workers_receive_scoped_context_and_enforced_reserve(self):
        tender, response = self.seed_attachments()
        projects.touch_session(self.root, self.sid, "旧会话")
        projects.append_turn(self.root, self.sid, "user", "OTHER_HISTORY_SECRET 不要复制到子任务。")
        unselected = uploads.save_upload(self.sid, "未选资料.txt", b"UNSELECTED_ATTACHMENT_SECRET")
        calls = []
        def fake_model(messages, **kwargs):
            calls.append((messages, kwargs))
            return {"content": json.dumps({"conclusions": [], "unresolved": ["测试模型意见待人工核验"]})}
        with patch.object(flow.workbench, "has_key", return_value=True), patch("llm.chat", side_effect=fake_model):
            done, _ = self.post("全面检查投标响应。", attachments=[tender["id"], response["id"]])
        self.assertTrue(done["ok"], done)
        self.assertEqual(len(calls), 2)
        for messages, kwargs in calls:
            encoded = json.dumps(messages, ensure_ascii=False)
            self.assertNotIn("OTHER_HISTORY_SECRET", encoded)
            self.assertNotIn("UNSELECTED_ATTACHMENT_SECRET", encoded)
            self.assertLessEqual(kwargs["max_tokens"], context.policy()["reserve"])
            self.assertEqual(len(messages), 2)
        self.assertEqual(done["collaboration"]["aggregate_metrics"]["model_calls"], 2)

    def test_all_experts_have_live_capability_api(self):
        from packing_assistant.expert_roster import list_experts
        for expert in list_experts():
            response = self.client.get(f"/api/experts/{expert.id}/capability")
            self.assertEqual(response.status_code, 200, expert.id)
            value = response.json()
            self.assertTrue(value["inputs"] and value["acceptance"] and value["steps"])
            self.assertTrue(all(tool["available"] for tool in value["tools"]))

    def test_cancelled_collaboration_is_restored_with_its_children(self):
        started = Event()
        def blocked(messages, **kwargs):
            started.set()
            deadline = time.monotonic() + 4
            while not kwargs["cancel_event"].is_set() and time.monotonic() < deadline:
                time.sleep(.01)
            raise InterruptedError("模型已停止")
        tender, response = self.seed_attachments()
        with ThreadPoolExecutor(max_workers=1) as pool, patch.object(flow.workbench, "has_key", return_value=True), \
             patch.object(demo_llm, "chat", side_effect=blocked):
            pending = pool.submit(self.post, "全面检查投标响应。", attachments=[tender["id"], response["id"]])
            self.assertTrue(started.wait(3))
            self.assertTrue(self.client.post(f"/api/sessions/{self.sid}/cancel").json()["cancel_requested"])
            done, _ = pending.result(timeout=4)
        self.assertEqual(done["state"], "cancelled")
        self.assertEqual(done["collaboration"]["state"], "cancelled")
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(restored["collaboration"]["parent_run_id"], done["collaboration"]["parent_run_id"])
        self.assertTrue(all(c["status"] == "cancelled" for c in restored["collaboration"]["children"]))
        self.assertFalse(turn_control.status(self.sid)["active"])
        self.assertTrue(restored["deliverables"])

    def test_budget_failure_is_reported_without_model_calls(self):
        tender, response = self.seed_attachments()
        with patch.object(flow.workbench, "has_key", return_value=True), patch.object(demo_llm, "chat") as model:
            done, _ = self.post("全面检查投标响应。", attachments=[tender["id"], response["id"]],
                workflow_budget={"total_tokens": 1024, "worker_tokens": 1024, "output_tokens": 128})
        self.assertFalse(done["ok"], done)
        self.assertEqual(done["collaboration"]["error_code"], "budget_exceeded")
        model.assert_not_called()

    def test_unwritable_summary_cache_does_not_hide_completed_files(self):
        tender, response = self.seed_attachments()
        cache = self.root / self.sid / "collaboration.summary.json"
        cache.mkdir(parents=True)
        done, _ = self.post("全面检查投标响应。", attachments=[tender["id"], response["id"]])
        self.assertTrue(done["ok"], done)
        self.assertIn("摘要缓存未保存", done["text"])
        self.assertTrue(done["deliverables"])
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(restored["collaboration"]["state"], "done")
        self.assertEqual({d["path"] for d in restored["deliverables"]}, {d["path"] for d in done["deliverables"]})
        self.assertFalse(list(cache.parent.glob(".collaboration-*.tmp")))

    def test_evidence_ranges_resolve_to_the_actual_selected_source(self):
        tender, response = self.seed_attachments()
        done, _ = self.post("全面检查投标响应。", attachments=[tender["id"], response["id"]])
        evidence = [e for c in done["collaboration"]["children"] for e in c["evidence"]]
        self.assertTrue(evidence)
        for item in evidence:
            resolved = self.client.get("/api/context/source", params={"session_id": self.sid,
                "source_id": item["source_id"], "start": item["start"], "end": item["end"]})
            self.assertEqual(resolved.status_code, 200, resolved.text)
            self.assertEqual(resolved.json()["text"], item["quote"])

    def test_cli_runtime_uses_shared_routes_and_real_parallel_workflow(self):
        from packing_assistant.runtime.agent_loop import run_agent
        from packing_assistant.runtime.scheduler import Scheduler
        scheduler = Scheduler()
        done = run_agent("全面检查投标响应，汇总缺项。\n招标正文：\n" + TENDER,
                         session_id=self.sid, scheduler=scheduler)
        self.assertTrue(done["ok"], done)
        self.assertEqual(done["state"], "done")
        self.assertTrue(done["wrote"])
        self.assertEqual(len(done["collaboration"]["children"]), 2)
        self.assertNotIn(self.sid, scheduler._locks)
        for file in done["files"]:
            self.assertTrue(Path(file["path"]).is_file())
        daily = run_agent("整理日报，日期：2031年5月6日，部位：东桥。", session_id=self.sid, scheduler=scheduler)
        self.assertTrue(daily["ok"], daily)
        self.assertEqual(daily["skill"], "pm-daily")
        self.assertNotIn("collaboration", daily)
        ambiguous = run_agent("整理设计变更", session_id=self.sid, scheduler=scheduler)
        self.assertTrue(ambiguous["route"]["ambiguous"])
        self.assertFalse(ambiguous["wrote"])

    def test_cli_read_only_and_step_budget_prevent_workflow_writes(self):
        from packing_assistant.runtime.agent_loop import run_agent
        prompt = "全面检查投标响应并汇总缺项。\n" + TENDER
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}):
            readonly = run_agent(prompt, session_id=self.sid)
        self.assertFalse(readonly["wrote"], readonly)
        self.assertIn("只读", readonly["reply"])
        limited = run_agent(prompt, session_id=self.sid, max_steps=3)
        self.assertFalse(limited["ok"])
        self.assertEqual(limited["error_code"], "max_steps")
        self.assertFalse(list(self.root.rglob("*.docx")))


class ChildTransportTests(unittest.TestCase):
    def test_child_stop_closes_real_upstream_before_headers_and_during_body(self):
        for send_headers in (False, True):
            with self.subTest(send_headers=send_headers):
                server = ThreadingHTTPServer(("127.0.0.1", 0), BlockedModel)
                server.daemon_threads = True
                server.send_headers = send_headers
                server.started, server.disconnected, server.stop_probe = Event(), Event(), Event()
                server_thread = Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                stop, finished = Event(), Event()
                errors = []
                def request():
                    try:
                        demo_llm.chat([{"role": "user", "content": "本地连接测试"}], max_tokens=128, cancel_event=stop)
                    except Exception as exc:
                        errors.append(type(exc).__name__)
                    finally:
                        finished.set()
                config = {"api_key": "local-fixture", "model": "local-probe", "base_url": f"http://127.0.0.1:{server.server_port}"}
                worker = Thread(target=request, daemon=True)
                try:
                    with patch.object(demo_llm, "llm_config", return_value=config):
                        worker.start()
                        self.assertTrue(server.started.wait(3))
                        stop.set()
                        self.assertTrue(server.disconnected.wait(2), "upstream socket remained open")
                        self.assertTrue(finished.wait(2), "child request reader leaked")
                        self.assertTrue(errors)
                finally:
                    stop.set()
                    server.stop_probe.set()
                    server.shutdown()
                    server.server_close()
                    server_thread.join(2)
                    worker.join(2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
