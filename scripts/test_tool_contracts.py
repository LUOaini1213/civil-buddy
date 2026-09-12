"""Tool discovery and runtime enforce the same typed contracts, without model I/O."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "demo")]
from packing_assistant.runtime.tool_engine import ToolEngine, default_engine
from packing_assistant.runtime.tool_contracts import obj
import mcp_surface


class ToolContractsTests(unittest.TestCase):
    def test_bad_types_missing_and_unknown_fields_never_reach_handler(self):
        handler = Mock(return_value={"ok": True})
        engine = ToolEngine()
        engine.register("typed", handler, input_schema=obj({"confirm": {"type": "boolean"},
            "items": {"type": "array", "items": {"type": "integer"}}}, ("confirm",)))
        for args in ([], "bad", {}, {"confirm": "true"}, {"confirm": True, "typo": 1},
                     {"confirm": True, "items": [True]}, {"confirm": True, "items": ["1"]}):
            result = engine.execute("typed", args)
            self.assertEqual(result["error_code"], "invalid_args", result)
        handler.assert_not_called()
        self.assertTrue(engine.execute("typed", {"confirm": False, "items": [1]})["ok"])

    def test_output_contract_rejects_false_success(self):
        engine = ToolEngine()
        engine.register("typed", lambda _: {"ok": True, "files": "not-a-list"},
                        output_schema=obj({"files": {"type": "array"}}, ("files",), extra=True))
        result = engine.execute("typed")
        self.assertFalse(result["ok"])
        self.assertTrue(result["contract_error"])

    def test_failed_handler_keeps_original_error(self):
        engine = ToolEngine()
        engine.register("typed", lambda _: {"ok": False, "error_code": "missing_source"},
                        output_schema=obj({"files": {"type": "array"}}, ("files",)))
        self.assertEqual(engine.execute("typed")["error_code"], "missing_source")

    def test_all_builtin_tools_expose_copy_safe_schemas(self):
        engine = default_engine()
        rows = engine.schemas_for()
        self.assertGreaterEqual(len(rows), 74)
        for row in rows:
            self.assertEqual(row["input_schema"]["type"], "object")
            self.assertEqual(row["output_schema"]["type"], "object")
            self.assertIs(row["input_schema"]["additionalProperties"], False)
        rows[0]["input_schema"]["properties"].clear()
        self.assertTrue(engine.schemas_for()[0]["input_schema"]["properties"])

    def test_null_solver_remains_explicitly_disconnected(self):
        result = default_engine().execute("pack-ship__health", {"solver": None}, expert_id="pack-ship")
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["connected"])

    def test_mcp_discovery_and_string_confirmation_validation(self):
        tools = mcp_surface.list_tools(expert_id="construction")
        scheme = next(t for t in tools if t["name"] == "construction__scheme_draft")
        self.assertEqual(scheme["inputSchema"]["properties"]["confirm_ok"]["type"], "boolean")
        self.assertIn("files", scheme["outputSchema"]["properties"])
        with patch("packing_assistant.runtime.agent_loop.run_agent") as runner:
            result = mcp_surface.call_tool("civil.turn", {"text": "draft", "confirm_ok": "false"}, expert_id="construction")
            self.assertEqual(result["error_code"], "invalid_args")
            runner.assert_not_called()

    def test_mcp_rejects_nonobject_and_unknown_field(self):
        self.assertEqual(mcp_surface.call_tool("civil.turn", ["bad"])["error_code"], "invalid_args")
        result = mcp_surface.call_tool("search_kb", {"qurey": "test"}, expert_id="pm-daily")
        self.assertEqual(result["error_code"], "invalid_args")

    def test_exclusive_permission_survives_contract(self):
        result = default_engine().execute("construction__scheme_draft", {"text": "draft"}, expert_id="pm-daily")
        self.assertEqual(result["error_code"], "permission_denied")


if __name__ == "__main__":
    unittest.main(verbosity=2)
