"""Real workbench HTTP regression for addressing, quoted actions, and negation."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import test_workbench_flow as flow


class ReadonlyRoutingTests(unittest.TestCase):
    setUp = flow.WorkbenchFlowTests.setUp
    post = flow.WorkbenchFlowTests.post

    def readonly(self, message: str, **fields):
        self.sid = "readonly-" + uuid4().hex[:16]
        done, _ = self.post(message, **fields)
        self.assertTrue(done["ok"], done)
        self.assertEqual(done["intent"], "chat", done)
        self.assertFalse(done["wrote"], done)
        self.assertEqual(done["deliverables"], [], done)
        audit = self.client.get(f"/api/harness/audit/{self.sid}").json()
        self.assertEqual(audit["counts"]["tools"], 0, audit)
        self.assertEqual(audit["counts"]["writes"], 0, audit)
        self.assertFalse([p for p in (self.root / self.sid).rglob("*")
                          if p.suffix.lower() in {".md", ".docx", ".xlsx"}])
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(restored["deliverables"], [])
        self.assertEqual(restored["transcript"][0]["text"], message)
        self.assertEqual(restored["transcript"][-1]["text"], done["text"])
        self.no_model.assert_not_called()
        return done

    def test_explicit_post_prefixes_answer_without_tools_or_documents(self):
        for prefix in ("@pm-daily", "$pm-daily", "@项目日报", "召唤 项目日报"):
            with self.subTest(prefix=prefix):
                self.readonly(prefix + " 请继续解释资料核对的注意点？")
        self.readonly("@construction 请继续解释专项施工方案检查注意点？\n我明白，将由持证人员签认")

    def test_negated_and_quoted_operations_are_only_conversation(self):
        for text in ("@项目日报 请不要生成日报", "请不要生成日报", "不用生成日报，只解释资料核对注意点",
                     "请解释“先整理再生成日报”的含义", "请解释为什么先检查再生成日报",
                     "解释 `先检查再生成日报` 的流程", "“生成并检查日报”按钮安全吗？"):
            with self.subTest(text=text):
                self.readonly(text, expert_ids=["pm-daily"])

    def test_clear_explanation_then_generation_still_produces_real_draft(self):
        for text in ("@项目日报 解释后生成项目日报", "$pm-daily 解释并生成日报",
                     "请解释为什么需要核对资料，然后生成项目日报"):
            with self.subTest(text=text):
                self.sid = "draft-" + uuid4().hex[:16]
                done, _ = self.post(text, expert_ids=["pm-daily"])
                self.assertTrue(done["ok"] and done["wrote"], done)
                self.assertEqual(done["intent"], "both", done)
                self.assertEqual({Path(item["path"]).suffix for item in done["deliverables"]},
                                 {".md", ".docx", ".xlsx"})
                for item in done["deliverables"]:
                    self.assertTrue(Path(item["path"]).is_file())
                self.no_model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
