"""Offline adversarial contracts for the fixed-loopback research adapters."""
from copy import deepcopy
from email.message import Message
from io import BytesIO
from pathlib import Path
import sys
import time
import re
import subprocess
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packing_assistant.runtime.tool_engine import default_engine
from packing_assistant.tools import readonly_sources as sources
from packing_assistant.runtime.research_demo import _explicit_months, _intent_guard, _map_model_call

ARGS = {"query_id": "brand_compare", "parameters": {"start_month": "2026-01", "end_month": "2026-08", "makers": ["BYD", "TESLA"]}}
SOURCE = {"dataset": "test-registrations", "version": "fixture-v1", "data_asof": "2026-08-31",
          "hashes": {"fixture_sha256": "a" * 64}}
JPJ = {**deepcopy(ARGS), "rows": [{"maker": "BYD", "registrations": 10}], "columns": ["maker", "registrations"],
       "source": SOURCE, "sql": "SELECT maker, SUM(registrations) FROM fixture WHERE month BETWEEN %s AND %s GROUP BY maker",
       "metric_definition": "Fixture registration counts; not real JPJ evidence."}
HIT = {"document_id": "fixture", "title": "Test only", "url": "https://ntrs.nasa.gov/citations/fixture", "sha256": "a" * 64,
       "text": "constant current", "location": {"kind": "paragraph", "section": "body", "paragraph": 1, "start_char": 10, "end_char": 26},
       "entities": [{"type": "method", "value": "constant current", "evidence": {"quote": "constant current", "start_char": 0, "end_char": 16}}], "relations": []}
LIT = {"hits": [HIT], "method": "fixture", "corpus_version": "fixture-v1"}
CATALOG = {"makers": ["BYD", "TESLA", "TOYOTA", "GAC", "GAC AION"], "fuels": ["electric", "diesel", "petrol", "hybrid_diesel", "hybrid_petrol"]}


class ReadonlySourcesTests(unittest.TestCase):
    def call(self, name, args, response=None):
        with patch.object(sources, "_request", return_value=deepcopy(response)) as request:
            result = default_engine().execute(name, args, intent="chat")
            return result, request

    def test_registration_policy_and_copy_safe_schemas(self):
        engine = default_engine()
        for name in sources.TOOLS:
            self.assertIn(name, engine.tools)
            self.assertFalse(engine.tools[name].writes)
            self.assertFalse(engine.tools[name].input_schema["additionalProperties"])
        self.assertEqual(engine.execute("write_deliverable", {"path": "test.txt", "text": "x"}, intent="chat")["error_code"], "permission_denied")
        self.assertEqual(engine.execute("construction__scheme_draft", {"text": "x"}, expert_id="pm-daily")["error_code"], "permission_denied")

    def test_missing_parameters_asks_without_io(self):
        for name, args in (("jpj.query", {}), ("jpj.query", {"query_id": "brand_compare"}), ("literature.search", {})):
            result, request = self.call(name, args)
            self.assertEqual(result["error_code"], "missing_parameters")
            self.assertTrue(result["question"])
            request.assert_not_called()

    def test_unknown_parameters_metric_and_cross_tab_rejected(self):
        cases = [dict(ARGS, url="http://evil.invalid"), dict(ARGS, sql="DROP TABLE x"),
                 {"query_id": "brand_compare", "parameters": {**ARGS["parameters"], "fuel": "electric"}},
                 {"query_id": "brand_compare", "parameters": {**ARGS["parameters"], "metric": "sales"}},
                 {"query_id": "brand_compare", "parameters": {**ARGS["parameters"], "typo": "x"}},
                 {"query_id": "brand_compare", "parameters": {**ARGS["parameters"], "makers": ["BYD", "byd"]}}]
        for args in cases:
            result, request = self.call("jpj.query", args)
            self.assertFalse(result["ok"], args)
            request.assert_not_called()

    def test_dates_limits_and_types(self):
        cases = [{"query_id": "monthly_registrations", "parameters": {"start_month": "2026-13", "end_month": "2026-08"}},
                 {"query_id": "monthly_registrations", "parameters": {"start_month": "2026-09", "end_month": "2026-08"}},
                 {"query_id": "maker_ranking", "parameters": {"start_month": "2026-01", "end_month": "2026-08", "limit": 31}}]
        for args in cases:
            result, request = self.call("jpj.query", args)
            self.assertFalse(result["ok"])
            request.assert_not_called()
        for limit in (0, 11, True, "5"):
            result, request = self.call("literature.search", {"query": "battery", "limit": limit})
            self.assertFalse(result["ok"])
            request.assert_not_called()
        result, request = self.call("literature.search", {"query": "x" * 201})
        self.assertFalse(result["ok"])
        request.assert_not_called()

    def test_success_preserves_sql_parameters_hashes(self):
        result, _ = self.call("jpj.query", ARGS, JPJ)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"], JPJ)
        self.assertTrue(result["policy"]["allow"])

    def test_normalized_brands_are_semantically_equal(self):
        args = deepcopy(ARGS)
        args["parameters"]["makers"] = [" byd ", "tesla"]
        self.assertTrue(self.call("jpj.query", args, JPJ)[0]["ok"])

    def test_bad_response_and_changed_filter_are_not_success(self):
        variants = [dict(JPJ, sql=None), dict(JPJ, source={}), dict(JPJ, rows=[{"unexpected": 99}])]
        changed = deepcopy(JPJ)
        changed["parameters"]["start_month"] = "2025-01"
        variants.append(changed)
        for response in variants:
            result, _ = self.call("jpj.query", ARGS, response)
            self.assertEqual(result["error_code"], "invalid_upstream_response")
            self.assertFalse(result["ok"])

    def test_citations_preserved_and_mismatches_rejected(self):
        result, _ = self.call("literature.search", {"query": "constant current", "limit": 5}, LIT)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"], LIT)
        for bad in ("quote", "offset", "hash", "url"):
            response = deepcopy(LIT)
            hit = response["hits"][0]
            if bad == "quote":
                hit["entities"][0]["evidence"]["quote"] = "fabricated"
            elif bad == "offset":
                hit["entities"][0]["evidence"]["start_char"] = 1
            elif bad == "hash":
                hit["sha256"] = "not-a-hash"
            else:
                hit["url"] = "javascript:alert(1)"
            result, _ = self.call("literature.search", {"query": "battery"}, response)
            self.assertEqual(result["error_code"], "invalid_upstream_response", bad)

    def test_timeout_unavailable_and_http_rejections(self):
        for error, expected in ((TimeoutError(), "timeout"), (URLError("offline"), "service_unavailable"),
                                (HTTPError("unused", 302, "redirect", {}, None), "upstream_redirect_denied")):
            with patch.object(sources, "_request", side_effect=error):
                result = default_engine().execute("jpj.query", ARGS)
            self.assertEqual(result["error_code"], expected)
        headers = Message()
        headers["Content-Type"] = "application/json"
        error = HTTPError("unused", 422, "bad", headers, BytesIO(b'{"error":{"code":"out_of_range","message":"Month unavailable","details":{}}}'))
        with patch.object(sources, "_request", side_effect=error):
            result = default_engine().execute("jpj.query", ARGS)
        self.assertEqual(result["upstream_error"]["code"], "out_of_range")

    def test_engine_timeout_stays_active(self):
        engine = default_engine()
        engine.tools["jpj.catalog"].timeout_s = .005
        with patch.object(sources, "_request", side_effect=lambda *_: time.sleep(.03)):
            result = engine.execute("jpj.catalog", {})
        self.assertEqual(result["error_code"], "timeout")
        time.sleep(.04)

    def test_network_cannot_redirect_or_use_environment_proxy(self):
        with patch.object(sources, "build_opener") as builder:
            headers = Message()
            headers["Content-Type"] = "application/json"
            response = Mock(headers=headers)
            response.read.return_value = b'{}'
            builder.return_value.open.return_value.__enter__.return_value = response
            sources._request("jpj.catalog", {})
            handlers = builder.call_args.args
            self.assertEqual(handlers[0].proxies, {})
            self.assertIsInstance(handlers[1], sources._NoRedirect)
            self.assertIsNone(handlers[1].redirect_request(None, None, 302, "", {}, "http://evil.invalid"))
            req = builder.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, "http://127.0.0.1:8777/api/catalog")

    def test_original_prompt_guard_stops_model_metric_substitution_and_guessed_dates(self):
        self.assertEqual(_intent_guard("2026年1-8月BYD销量", "jpj.query", ARGS)["error_code"], "unsupported_metric")
        self.assertEqual(_intent_guard("对比BYD和TESLA登记量", "jpj.query", ARGS)["error_code"], "missing_parameters")
        self.assertIsNone(_intent_guard("对比2026年1月至8月BYD和TESLA的汽车登记量", "jpj.query", ARGS, CATALOG))
        self.assertEqual(_intent_guard("2026-01至2026-08 BYD纯电注册量", "jpj.query", ARGS, CATALOG)["error_code"], "unsupported_dimension")
        self.assertEqual(_explicit_months("2026年1-8月"), {"2026-01", "2026-08"})

    def test_scope_guard_binds_all_filters_and_ordered_endpoints(self):
        dates = {"start_month": "2026-01", "end_month": "2026-08"}
        cases = [
            ("Compare BYD and TESLA registrations from 2026-01 to 2026-08", {"query_id": "monthly_registrations", "parameters": dates}),
            ("electric registrations from 2026-01 to 2026-08", {"query_id": "monthly_registrations", "parameters": dates}),
            ("TOYOTA electric registrations from 2026-01 to 2026-08", {"query_id": "monthly_registrations", "parameters": {**dates, "maker": "TOYOTA"}}),
            ("registrations from 2026-01 to 2026-08", {"query_id": "monthly_registrations", "parameters": {**dates, "maker": "TOYOTA"}}),
            ("Compare BYD and TESLA registrations from 2026-01 to 2026-08", {"query_id": "brand_compare", "parameters": {**dates, "end_month": "2026-01", "makers": ["BYD", "TESLA"]}}),
        ]
        for prompt, mapped in cases:
            with self.subTest(prompt=prompt):
                result = _intent_guard(prompt, "jpj.query", mapped, CATALOG)
                self.assertIsNotNone(result)
                self.assertFalse(result["ok"])
                self.assertFalse(result["executed"])
        self.assertIsNone(_intent_guard("Compare BYD and TESLA registrations from 2026-01 to 2026-08", "jpj.query", ARGS, CATALOG))
        self.assertIsNone(_intent_guard("electric registrations from 2026-01 to 2026-08", "jpj.query",
            {"query_id": "fuel_monthly", "parameters": {**dates, "fuel": "electric"}}, CATALOG))
        self.assertIsNone(_intent_guard("GAC AION registrations from 2026-01 to 2026-08", "jpj.query",
            {"query_id": "monthly_registrations", "parameters": {**dates, "maker": "GAC AION"}}, CATALOG))

    def test_unknown_qualifiers_and_catalog_failure_ask_instead_of_dropping_scope(self):
        for prompt in ("Compare UNKNOWNBRAND and TESLA registrations from 2026-01 to 2026-08",
                       "只看周末的2026年1月至8月BYD和TESLA登记量",
                       "Compare BYD and TESLA registrations excluding taxis from 2026-01 to 2026-08"):
            self.assertEqual(_intent_guard(prompt, "jpj.query", ARGS, CATALOG)["error_code"], "missing_parameters")
        self.assertEqual(_intent_guard("Compare BYD and TESLA registrations from 2026-01 to 2026-08", "jpj.query", ARGS)["error_code"], "missing_parameters")

    def test_separate_months_and_unbound_brand_grouping_do_not_become_totals(self):
        cases = [("registrations by brand from 2026-01 to 2026-08", {"query_id": "monthly_registrations", "parameters": {"start_month": "2026-01", "end_month": "2026-08"}}),
                 ("Compare BYD and TESLA registrations in 2026-01 and 2026-08", ARGS),
                 ("对比2026年1月和2026年8月BYD和TESLA的登记量", ARGS)]
        for prompt, mapped in cases:
            self.assertEqual(_intent_guard(prompt, "jpj.query", mapped, CATALOG)["error_code"], "missing_parameters")

    def test_page_uses_text_nodes_for_untrusted_sources(self):
        html = (ROOT / "demo" / "research_tools.html").read_text(encoding="utf-8")
        self.assertIn("textContent", html)
        self.assertNotIn("innerHTML", html)
        script = re.search(r"<script>([\s\S]*?)</script>", html).group(1)
        result = subprocess.run(["node", "--check"], input=script, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_model_adapter_only_nests_exact_arguments(self):
        flat = {"start_month": "2026-01", "end_month": "2026-08", "makers": ["BYD", "TESLA"], "unexpected": "must not be dropped"}
        name, mapped = _map_model_call("jpj_brand_compare", flat)
        self.assertEqual(name, "jpj.query")
        self.assertEqual(mapped, {"query_id": "brand_compare", "parameters": flat})
        result, request = self.call(name, mapped)
        self.assertFalse(result["ok"])
        request.assert_not_called()
        for name, arguments in (({}, {}), ([], {}), ("jpj_brand_compare", [])):
            with self.assertRaises(ValueError):
                _map_model_call(name, arguments)


if __name__ == "__main__":
    unittest.main(verbosity=2)
