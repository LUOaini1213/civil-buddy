#!/usr/bin/env python3
"""中文 | English on the workbench: the catalogue is complete both ways, the server answers in the page's language,
and the switch relaxes nothing.

* every message the page asks for (tr("…") in its scripts, data-i18n / data-i18n-attr in index.html) has an English
  entry in demo/static/i18n/en.js, and every entry is still asked for; no Chinese literal is left outside tr()
  except the allow-listed data (the sign-off sentences, words matched against what is typed or what the server
  wrote); no Chinese text in the page's markup is left unmarked;
* English entries keep their {0} {1} fields, carry no Chinese except the Chinese sign-off sentence they quote, and
  use no emoji / dingbat code points (the page's symbol rule);
* workbench/posts_en.json names exactly the seed's 66 posts and 16 categories, and posts-en.js is what
  scripts/gen_cb_posts.py writes from it;
* the server: an error detail, a status line, the offline answer and the high-risk sign-off notice come back in
  English for X-Civil-Lang: en (or cookie cb_lang=en), in Chinese otherwise; the header wins over the cookie;
* the switch changes wording only: for the same request and the same typed sentence, what is approved, routed and
  held for sign-off is identical with the page in Chinese, in English or with no language at all.

    python scripts/test_workbench_i18n.py        (registered in scripts/check_project.py as workbench-i18n)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "demo"))
sys.path.insert(0, str(ROOT))

import i18n_scan as scan  # noqa: E402

OUT = ROOT / "output" / f"i18n-test-{os.getpid()}"
HAN = re.compile(r"[\u3400-\u9fff]")
DINGBATS = re.compile(r"[\u2600-\u27bf\U0001f000-\U0001faff\ufe0f]")


#: messages that reach tr() as data rather than as a literal: the built-in project's name as demo/projects.py sends it
DATA_MESSAGES = {"未归类"}


def page_messages() -> list[str]:
    ids: list[str] = []
    for name in scan.SCRIPTS:
        for m in scan.message_ids((scan.STATIC / name).read_text(encoding="utf-8")):
            if m not in ids:
                ids.append(m)
    for m in scan.html_ids((scan.STATIC / "index.html").read_text(encoding="utf-8")):
        if m not in ids:
            ids.append(m)
    return ids


class Catalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.en = scan.english_dictionary()
        cls.ids = page_messages()

    def test_every_message_has_english_and_nothing_is_stale(self):
        missing = [m for m in self.ids + sorted(DATA_MESSAGES) if m not in self.en]
        stale = [k for k in self.en if k not in self.ids and k not in DATA_MESSAGES]
        self.assertEqual(missing, [], "messages without an English entry")
        self.assertEqual(stale, [], "English entries no message asks for")
        self.assertGreater(len(self.ids), 700)

    def test_no_chinese_literal_outside_tr_and_no_unmarked_markup(self):
        for name in scan.SCRIPTS:
            with self.subTest(script=name):
                self.assertEqual(scan.unwrapped((scan.STATIC / name).read_text(encoding="utf-8")), [])
        self.assertEqual(scan.html_uncovered((scan.STATIC / "index.html").read_text(encoding="utf-8")), [])

    def test_english_entries_keep_fields_and_the_symbol_rule(self):
        from packing_assistant.runtime.civil_config import CONFIRM

        for zh, en in self.en.items():
            with self.subTest(message=zh[:40]):
                self.assertEqual(sorted(set(re.findall(r"\{\d+\}", zh))), sorted(set(re.findall(r"\{\d+\}", en))))
                self.assertIsNone(DINGBATS.search(en))
                rest = en.replace(CONFIRM, "").replace("界面语言", "")
                self.assertIsNone(HAN.search(rest), en)

    def test_the_sign_off_sentences_are_not_translated_away(self):
        from packing_assistant.runtime.civil_config import CONFIRM, CONFIRM_EN

        app = (scan.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn(f'const CB_SIGNOFF = ["{CONFIRM}", "{CONFIRM_EN}"];', app)
        label = next(k for k in self.en if k.startswith("高风险任务确认"))
        self.assertIn(CONFIRM_EN, self.en[label])
        self.assertIn(CONFIRM, self.en[label])         # the Chinese sentence stays accepted, and the page says so
        card = next(k for k in self.en if "cb-apr-ack" in k)
        self.assertIn(CONFIRM_EN, self.en[card])
        self.assertIn(CONFIRM, self.en[card])

    def test_every_server_message_has_english(self):
        """tr("…") in the server's own modules: each literal has an entry in demo/ui_lang.py's table."""
        import ast
        import ui_lang

        seen = 0
        for path in sorted((ROOT / "demo").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr" and node.args
                        and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                    seen += 1
                    with self.subTest(file=path.name, message=node.args[0].value[:40]):
                        self.assertIn(node.args[0].value, ui_lang.EN)
                        fields = set(re.findall(r"\{(\w+)\}", node.args[0].value))
                        self.assertEqual(fields, set(re.findall(r"\{(\w+)\}", ui_lang.EN[node.args[0].value])))
        self.assertGreater(seen, 40)
        for zh, en in ui_lang.EN.items():
            with self.subTest(entry=zh[:40]):
                self.assertIsNone(HAN.search(en), en)
                self.assertIsNone(DINGBATS.search(en), en)

    def test_page_loads_the_switch_before_anything_draws(self):
        html = (scan.STATIC / "index.html").read_text(encoding="utf-8")
        order = [html.index(s) for s in ('src="/static/i18n/en.js', 'src="/static/i18n.js', "CB_I18N.apply(document)",
                                          'src="/static/i18n/posts-en.js', 'src="/static/app.js')]
        self.assertEqual(order, sorted(order))
        self.assertIn('data-cb-lang="zh"', html)
        self.assertIn('data-cb-lang="en"', html)


class Posts(unittest.TestCase):
    def test_posts_en_names_exactly_the_seed(self):
        seed = json.loads((ROOT / "workbench" / "seed.json").read_text(encoding="utf-8"))
        english = json.loads((ROOT / "workbench" / "posts_en.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(english["posts"]), sorted(e["id"] for e in seed["experts"]))
        self.assertEqual(sorted(english["categories"]), sorted(c["id"] for c in seed["categories"]))
        for eid, row in english["posts"].items():
            with self.subTest(post=eid):
                for key in ("name", "title", "delivers"):
                    self.assertTrue(row[key].strip())
                    self.assertIsNone(HAN.search(row[key]))
        names = [row["name"] for row in english["posts"].values()]
        self.assertEqual(len(names), len(set(names)), "two posts share an English name")
        # the domain terms the task called out
        self.assertEqual(english["posts"]["safety-brief"]["name"], "Safety briefing")
        self.assertEqual(english["posts"]["pm-daily"]["name"], "Daily site report")
        self.assertIn("Tender", english["categories"]["bid"]["name"])

    def test_posts_en_js_is_the_generated_one(self):
        text = (scan.STATIC / "i18n" / "posts-en.js").read_text(encoding="utf-8")
        shipped = json.loads(text[text.index("{"):text.rindex("}") + 1])
        seed = json.loads((ROOT / "workbench" / "seed.json").read_text(encoding="utf-8"))
        english = json.loads((ROOT / "workbench" / "posts_en.json").read_text(encoding="utf-8"))
        expected = {e["id"]: {"name": english["posts"][e["id"]]["name"], "title": english["posts"][e["id"]]["title"],
                              "delivers": english["posts"][e["id"]]["delivers"],
                              "category_name": english["categories"][e["category"]]["name"]}
                    for e in seed["experts"]}
        self.assertEqual(shipped, expected, "run scripts/gen_cb_posts.py")


class Language(unittest.TestCase):
    def test_normalize_and_force(self):
        from packing_assistant.runtime.reply_language import english_request, normalize_language, using_page_language

        self.assertEqual([normalize_language(v) for v in ("en", "EN-gb", "zh-CN", "zh", "fr", "", None, "en;q=1")],
                         ["en", "en", "zh", "zh", "", "", "", ""])
        self.assertFalse(english_request("写一份日报"))
        self.assertTrue(english_request("Draft the daily report"))
        with using_page_language("en"):
            self.assertTrue(english_request("写一份日报"))
        with using_page_language("zh"):
            self.assertTrue(english_request("Draft the daily report"))   # an English request stays English
            self.assertFalse(english_request("写一份日报"))
        self.assertFalse(english_request("写一份日报"))

    def test_english_sample_prompts_route_like_the_chinese_ones(self):
        """The start card's samples prefill English text on an English page; each must reach the same posts."""
        from store import resolve_mentions
        from task_router import route_task

        en = scan.english_dictionary()
        app = (scan.STATIC / "app.js").read_text(encoding="utf-8")
        block = app[app.index("  const samples = {"):]
        block = block[:block.index("};")]
        samples = [scan.message_ids(line)[0] for line in block.splitlines() if "tr(" in line]
        self.assertEqual(len(samples), 6)
        for zh in samples:
            routes = []
            for text in (zh, en[zh]):
                r = route_task(text, resolve_mentions(text))
                routes.append((r["intent"], r["expert_ids"], r.get("workflow"), r["ambiguous"]))
            with self.subTest(sample=zh[:30]):
                self.assertEqual(routes[0], routes[1])

    def test_localize_route_keeps_what_it_routes_on(self):
        import ui_lang
        from task_router import route_task

        for text in ("帮我做个签证", "写一份技术会审纪要和变更签证", "根据附件综合检查投标响应", "@项目日报 写一份日报"):
            route = route_task(text, [])
            with ui_lang.using_page_language("en"):
                shown = ui_lang.localize_route(route)
            with self.subTest(text=text):
                self.assertEqual(shown["expert_ids"], route["expert_ids"])
                self.assertEqual(shown.get("workflow"), route.get("workflow"))
                self.assertEqual(shown.get("ambiguous"), route.get("ambiguous"))
                self.assertEqual([c["expert_ids"] for c in shown.get("candidates") or []],
                                 [c["expert_ids"] for c in route.get("candidates") or []])
                self.assertEqual([(s["id"], s.get("expert_id"), s.get("depends_on")) for s in shown.get("steps") or []],
                                 [(s["id"], s.get("expert_id"), s.get("depends_on")) for s in route.get("steps") or []])
                self.assertIsNone(HAN.search(shown["reason"] or ""), shown["reason"])
            with ui_lang.using_page_language("zh"):
                self.assertEqual(ui_lang.localize_route(route), route)


def sse(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.split("\n\n"):
        lines = block.splitlines()
        name = next((line[6:].strip() for line in lines if line.startswith("event:")), "")
        data = "".join(line[5:].strip() for line in lines if line.startswith("data:"))
        if name and data:
            out.append((name, json.loads(data)))
    return out


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        os.environ["CIVIL_OUT_ROOT"] = str(OUT)
        os.environ.setdefault("CIVIL_SANDBOX_ROOTS", str(ROOT))
        for key in ("CIVIL_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "CIVIL_TOKEN"):
            os.environ.pop(key, None)
        from fastapi.testclient import TestClient
        import app

        cls.client = TestClient(app.app)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(OUT, ignore_errors=True)

    def chat(self, message: str, headers: dict | None = None, **body) -> list[tuple[str, dict]]:
        self.client.cookies.clear()
        res = self.client.post("/api/chat", json={"message": message, "session_id": uuid4().hex[:12], **body},
                               headers=headers or {})
        self.assertEqual(res.status_code, 200, res.text[:300])
        return sse(res.text)

    def test_error_details_follow_the_page(self):
        path = "/api/experts/no-such-post/capability"
        self.client.cookies.clear()
        self.assertEqual(self.client.get(path).json()["detail"], "岗位能力契约不存在")
        self.assertEqual(self.client.get(path, headers={"X-Civil-Lang": "en"}).json()["detail"],
                         "No capability contract for this post")
        self.client.cookies.set("cb_lang", "en")
        self.assertEqual(self.client.get(path).json()["detail"], "No capability contract for this post")
        self.assertEqual(self.client.get(path, headers={"X-Civil-Lang": "zh"}).json()["detail"], "岗位能力契约不存在")
        self.client.cookies.clear()
        # a 400 from prepare_turn (a ValueError on the way out) and a formatted one
        res = self.client.post("/api/chat", json={"message": "x", "expert_ids": ["no-such-post"]}, headers={"X-Civil-Lang": "en"})
        self.assertEqual((res.status_code, res.json()["detail"]), (400, "Choose valid posts, at most 8 at a time"))
        res = self.client.post("/api/projects", json={"name": "x" * 61}, headers={"X-Civil-Lang": "en"})
        if res.status_code == 400:
            self.assertEqual(res.json()["detail"], "A project name has at most 60 characters")

    def test_turn_notes_follow_the_page(self):
        zh = self.chat("你好")
        en = self.chat("你好", {"X-Civil-Lang": "en"})
        status_zh = [d["text"] for e, d in zh if e == "status" and d.get("phase") == "understand"]
        status_en = [d["text"] for e, d in en if e == "status" and d.get("phase") == "understand"]
        self.assertEqual((status_zh, status_en), (["识别任务并选择岗位"], ["Understanding the task and choosing posts"]))
        done_zh = next(d for e, d in zh if e == "done")
        done_en = next(d for e, d in en if e == "done")
        self.assertTrue(done_zh["text"].startswith("我是 Civil Buddy"), done_zh["text"][:60])
        self.assertTrue(done_en["text"].startswith("I am Civil Buddy"), done_en["text"][:60])
        self.assertTrue(done_en["context"]["note"].startswith("The full request is about "), done_en["context"]["note"])
        self.assertTrue(done_zh["context"]["note"].startswith("完整请求约 "), done_zh["context"]["note"])

    def test_sign_off_notice_is_english_on_an_english_page(self):
        from packing_assistant.runtime.civil_config import CONFIRM, CONFIRM_EN

        zh = next(d for e, d in self.chat("@安全交底 写一份高处作业安全交底") if e == "done")
        en = next(d for e, d in self.chat("@安全交底 写一份高处作业安全交底", {"X-Civil-Lang": "en"}) if e == "done")
        self.assertTrue(zh["hitl_pending"] and en["hitl_pending"])
        self.assertIn(f"「{CONFIRM}」", zh["text"])
        self.assertIn("high-risk post", en["text"])
        self.assertIn(CONFIRM_EN, en["text"])
        self.assertIn(CONFIRM, en["text"])              # the Chinese sentence is named as accepted too
        self.assertFalse(zh["wrote"] or en["wrote"])

    def test_sign_off_notice_is_in_one_language(self):
        """An English request on a Chinese page gets the English notice with the post's English name, not
        "安全交底 is a high-risk post"; a Chinese request on an English page gets it in English throughout."""
        mixed = next(d for e, d in self.chat("@safety-brief Draft a work-at-height safety briefing", {"X-Civil-Lang": "zh"})
                     if e == "done")
        self.assertTrue(mixed["hitl_pending"])
        self.assertTrue(mixed["text"].startswith("Safety briefing is a high-risk post"), mixed["text"][:80])
        en = next(d for e, d in self.chat("@安全交底 写一份高处作业安全交底", {"X-Civil-Lang": "en"}) if e == "done")
        self.assertTrue(en["text"].startswith("Safety briefing is a high-risk post"), en["text"][:80])

    def test_model_errors_and_source_titles_follow_the_page(self):
        import ui_lang

        with ui_lang.using_page_language("en"):
            self.assertEqual(ui_lang.localize("LLM HTTP 401：认证失败，请检查 API Key 和接口权限"),
                             "LLM HTTP 401: authentication failed; check the API key and its permissions")
            self.assertEqual(ui_lang.localize("模型响应超时，请稍后重试"), "The model timed out; retry later")
            self.assertEqual(ui_lang.localize("用户 · 第 3 条消息"), "User · message 3")
            self.assertEqual(ui_lang.localize("助手 · 第 12 条消息"), "Assistant · message 12")
        with ui_lang.using_page_language("zh"):
            self.assertEqual(ui_lang.localize("用户 · 第 3 条消息"), "用户 · 第 3 条消息")
        # every message demo/llm.py raises has an English entry (or the LLM HTTP pattern)
        import ast

        tree = ast.parse((ROOT / "demo" / "llm.py").read_text(encoding="utf-8"))
        raised = [node.args[0].value for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "LLMError" and node.args
                  and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)]
        hints = [node.value.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                 and getattr(node.targets[0], "id", "") == "hint" and isinstance(node.value, ast.Constant)]
        self.assertGreater(len(raised), 10)
        with ui_lang.using_page_language("en"):
            for text in raised + [f"LLM HTTP 500：{hint}" for hint in hints]:
                with self.subTest(text=text[:30]):
                    self.assertIsNone(HAN.search(ui_lang.localize(text)), ui_lang.localize(text))

    def test_the_switch_relaxes_nothing(self):
        """Same request, same typed sentence: the same approval, the same route, whatever the page's language."""
        from packing_assistant.runtime.civil_config import CONFIRM, CONFIRM_EN

        request = "@安全交底 写一份高处作业安全交底"
        cases = [("", request), (CONFIRM, request), (CONFIRM_EN, request), (" " + CONFIRM_EN + " ", request),
                 ("", request + " " + CONFIRM_EN), ("", CONFIRM_EN), ("i understand; a licensed person will sign this off.", request),
                 ("我明白", request)]
        for confirm_text, message in cases:
            outcomes = {}
            for lang in ("", "zh", "en"):
                headers = {"X-Civil-Lang": lang} if lang else {}
                done = next(d for e, d in self.chat(message, headers, confirm_text=confirm_text) if e == "done")
                route = done.get("route") or {}
                outcomes[lang] = (done["hitl_pending"], done["wrote"], bool(done["deliverables"]), done["skill"],
                                  tuple(route.get("expert_ids") or []), route.get("intent"))
            with self.subTest(confirm=confirm_text[:20], message=message[:30]):
                self.assertEqual(outcomes[""], outcomes["zh"])
                self.assertEqual(outcomes[""], outcomes["en"])
        # and the approved case really wrote a draft (so the parity above is not three refusals)
        done = next(d for e, d in self.chat(request, {"X-Civil-Lang": "en"}, confirm_text=CONFIRM_EN) if e == "done")
        self.assertFalse(done["hitl_pending"])
        self.assertIn("produced an internal discussion draft", done["text"])
        self.assertNotIn("high-risk post", done["text"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
