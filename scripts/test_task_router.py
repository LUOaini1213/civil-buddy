"""Workbench routing: task phrases, explicit selection, ambiguity and dependency."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demo.task_router import route_task
from packing_assistant.runtime.expert_skills import match_skill


class TaskRouterTests(unittest.TestCase):
    def test_frequent_tasks_route_without_requiring_long_post_names(self):
        for text, eid in (("检查投标响应", "bid-compliance"), ("整理日报", "pm-daily"),
                          ("帮我制定备份策略", "it-data"), ("帮我写钢构说明", "steel"),
                          ("整理会务清单", "admin-office")):
            with self.subTest(text=text):
                route = route_task(text)
                self.assertEqual(route["expert_ids"], [eid])
                self.assertEqual(route["intent"], "run")
                self.assertFalse(route["ambiguous"])
                self.assertEqual(route["workflow"], "")

    def test_educational_questions_are_not_write_or_collaboration_requests(self):
        for text in ("备份策略是什么？", "如何检查投标响应？", "投标综合检查需要哪些资料？", "钢结构说明能做什么？",
                     "解释一下土木资料整理", "说明一下招标响应检查", "聊聊备份策略", "是否支持生成日报模板",
                     "有哪些整理资料工具", "能否介绍生成模板的工具", "请帮我解释如何写钢构说明",
                     "请继续解释资料核对的注意点？", "继续讲解施工方案的检查流程", "再介绍备份策略的制定思路",
                     "进一步解释投标响应检查", "接着讨论日报整理"):
            with self.subTest(text=text):
                route = route_task(text)
                self.assertEqual(route["intent"], "chat")
                self.assertEqual(route["workflow"], "")

    def test_explicit_explanation_followed_by_deliverable_remains_both(self):
        for text in ("解释并生成备份策略", "介绍备份策略，然后生成一份模板", "先解释日报栏目，再整理项目日报",
                     "继续解释日报栏目，然后生成项目日报"):
            with self.subTest(text=text):
                self.assertEqual(route_task(text)["intent"], "both")
        self.assertEqual(route_task("继续整理项目日报")["intent"], "run")

    def test_all_hosts_import_the_same_rich_router(self):
        from packing_assistant.runtime.task_router import route_task as runtime_route
        self.assertIs(route_task, runtime_route)

    def test_addressing_prefixes_preserve_readonly_intent(self):
        for prefix in ("@pm-daily", "$pm-daily", "@项目日报", "召唤 项目日报", "召唤pm-daily："):
            for question in ("请继续解释资料核对的注意点？", "只解释资料核对注意点", "请先继续讲解日报整理流程"):
                with self.subTest(prefix=prefix, question=question):
                    route = route_task(prefix + " " + question)
                    self.assertEqual(route["intent"], "chat")
                    self.assertEqual(route["expert_ids"], ["pm-daily"])
                    self.assertEqual(route["workflow"], "")
        team = route_task("@bid-parse $bid-tech @bid-compliance 请解释综合投标响应检查的注意点")
        self.assertEqual(team["intent"], "chat")
        self.assertEqual(team["workflow"], "")
        self.assertEqual(team["expert_ids"], ["bid-parse", "bid-tech", "bid-compliance"])

    def test_polite_and_scoped_negation_does_not_authorize_generation(self):
        for text in ("请不要生成日报", "请暂时不要生成日报", "请帮我不要写日报", "我不想生成日报",
                     "不用生成日报，只解释资料核对注意点", "仅解释资料核对注意点，不需要生成日报",
                     "@项目日报 请不要生成日报", "$pm-daily 暂不整理日报，只介绍栏目"):
            with self.subTest(text=text):
                self.assertEqual(route_task(text)["intent"], "chat")
        route = route_task("请不要写施工方案，只整理日报")
        self.assertEqual(route["intent"], "run")
        self.assertEqual(route["expert_ids"], ["pm-daily"])

    def test_quoted_or_discussed_sequences_do_not_become_actions(self):
        for text in ("请解释“先整理再生成日报”的含义", "解释‘整理并生成日报’的注意事项",
                     "@项目日报 请解释「整理并生成日报」的含义", '请解释"整理后生成日报"按钮',
                     "解释 `先检查再生成日报` 的流程", "请解释为什么先检查再生成日报",
                     "请解释先检查再生成日报的流程", "请解释整理并生成日报的含义", "“生成并检查日报”按钮安全吗？"):
            with self.subTest(text=text):
                self.assertEqual(route_task(text)["intent"], "chat")

    def test_unquoted_followup_deliverables_still_require_execution(self):
        for text in ("解释后生成项目日报", "@项目日报 解释并生成日报", "$pm-daily 先解释日报栏目再生成项目日报",
                     "召唤 项目日报 请解释栏目，之后生成项目日报", "解释为什么核对资料，然后生成项目日报",
                     "解释“整理并生成日报”的含义，然后生成项目日报", "不要生成施工方案，解释后生成项目日报"):
            with self.subTest(text=text):
                route = route_task(text)
                self.assertEqual(route["intent"], "both")
                self.assertEqual(route["expert_ids"], ["pm-daily"])

    def test_explicit_single_post_never_expands_into_a_team(self):
        for text, ids in (("综合检查投标响应", ["bid-compliance"]),
                          ("@bid-parse 综合检查投标响应", None),
                          ("@招标解析 综合检查投标响应", None)):
            with self.subTest(text=text):
                route = route_task(text, ids)
                self.assertEqual(route["expert_ids"], ids or ["bid-parse"])
                self.assertEqual(route["workflow"], "")

    def test_selected_post_overrides_mentions_and_keeps_custom_ids_for_live_validation(self):
        self.assertEqual(route_task("@steel 写说明", ["pm-daily"])["expert_ids"], ["pm-daily"])
        self.assertEqual(route_task("整理资料", ["custom-adviser"])["expert_ids"], ["custom-adviser"])
        with self.assertRaises(ValueError):
            route_task("整理资料", ["../unknown"])

    def test_tender_review_has_real_parallel_dependencies(self):
        route = route_task("根据附件全面检查投标响应，汇总未解决事项")
        self.assertEqual(route["expert_ids"], ["bid-parse", "bid-tech", "bid-compliance"])
        self.assertEqual(route["workflow"], "tender-review")
        deps = {step["id"]: step["depends_on"] for step in route["steps"]}
        self.assertEqual(deps, {"parse": [], "tech": ["parse"], "compliance": ["parse"], "aggregate": ["tech", "compliance"]})

    def test_compound_request_keeps_user_order_and_sequential_dependencies(self):
        route = route_task("先招标解析，再准备施工方案")
        self.assertEqual(route["expert_ids"], ["bid-parse", "construction"])
        self.assertEqual(route["intent"], "run")
        self.assertEqual(route["steps"][1]["depends_on"], [route["steps"][0]["id"]])
        self.assertEqual(route["workflow"], "")

    def test_shared_alias_is_ambiguous_even_when_explicitly_prefixed(self):
        for text in ("整理设计变更", "@设计变更 整理草稿"):
            with self.subTest(text=text):
                route = route_task(text)
                self.assertTrue(route["ambiguous"])
                self.assertEqual(route["expert_ids"], [])
                self.assertEqual({c["expert_ids"][0] for c in route["candidates"]}, {"design-coord", "variation"})
                self.assertTrue(all(c["reason"] for c in route["candidates"]))

    def test_exact_id_disambiguates_shared_names(self):
        self.assertEqual(route_task("$variation 整理设计变更")["expert_ids"], ["variation"])
        self.assertEqual(route_task("@design-coord 整理设计变更")["expert_ids"], ["design-coord"])
        self.assertEqual(route_task("@steel-unregistered 写材料")["expert_ids"], [])

    def test_negated_task_does_not_steal_selection(self):
        route = route_task("不要写施工方案，只整理日报")
        self.assertEqual(route["expert_ids"], ["pm-daily"])
        self.assertEqual(route["intent"], "run")

    def test_specific_daily_task_and_unknown_text_do_not_guess_a_post(self):
        self.assertEqual(route_task("整理调度日报")["expert_ids"], ["dispatch"])
        self.assertEqual(route_task("你好")["expert_ids"], [])
        self.assertEqual(route_task("")["intent"], "chat")

    def test_legacy_shared_matcher_is_not_modified(self):
        self.assertIsNone(match_skill("帮我写一份备份策略"))
        self.assertEqual(match_skill("先招标解析，再准备施工方案"), "construction")


if __name__ == "__main__":
    unittest.main()
