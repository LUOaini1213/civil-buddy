"""Read-only adapters to two fixed local research services.

No URL, file, SQL, shell or credential inputs. Redirects and environment proxies
are disabled. The existing ToolEngine applies policy, timeout and audit gates.
The adapters preserve upstream provenance instead of generating factual answers.
"""
from __future__ import annotations

import json
import hashlib
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from urllib.parse import urlparse

TOOLS = ("jpj.catalog", "jpj.query", "literature.catalog", "literature.search")
ENDPOINTS = {
    "jpj.catalog": "http://127.0.0.1:8777/api/catalog",
    "jpj.query": "http://127.0.0.1:8777/api/query",
    "literature.catalog": "http://127.0.0.1:8778/api/catalog",
    "literature.search": "http://127.0.0.1:8778/api/search",
}
QUERY_PARAMS = {
    "monthly_registrations": {"start_month", "end_month", "maker", "metric"},
    "brand_compare": {"start_month", "end_month", "makers", "metric"},
    "maker_ranking": {"start_month", "end_month", "limit", "metric"},
    "fuel_monthly": {"start_month", "end_month", "fuel", "metric"},
}
MAX_BODY = 2 * 1024 * 1024
NETWORK_TIMEOUT = 4.0


def contract_for_source(name):
    from packing_assistant.runtime.tool_contracts import obj
    text = {"type": "string", "minLength": 1, "maxLength": 160}
    if name == "jpj.query":
        properties = {"query_id": {"type": "string", "enum": list(QUERY_PARAMS)},
                      "parameters": obj({"start_month": text, "end_month": text,
                          "maker": text, "makers": {"type": "array", "items": text},
                          "fuel": text, "metric": {"type": "string", "enum": ["registrations"]},
                          "limit": {"type": "integer"}})}
    elif name == "literature.search":
        properties = {"query": {"type": "string", "maxLength": 200}, "limit": {"type": "integer"}}
    else:
        properties = {}
    # Missing fields are handled as a clarification by the handler before I/O.
    return {"schema_version": "civil.tool.v1", "input_schema": obj(properties),
            "output_schema": obj({"ok": {"const": True}, "executed": {"const": True},
                                  "result": {"type": "object"}}, ("ok", "executed", "result"))}


def _failure(code, message, **details):
    return {"ok": False, "executed": False, "error_code": code, "reason": message, **details}


def _missing(fields, question):
    return _failure("missing_parameters", "请补充查询条件。", missing=fields, question=question,
                    status="needs_input")


def _validate_args(name, args):
    from packing_assistant.runtime.tool_contracts import validate
    issue = validate(args, contract_for_source(name)["input_schema"])
    if issue:
        return _failure("invalid_args", issue)
    if name == "jpj.query":
        if "query_id" not in args:
            return _missing(["query_id"], "请选择月度注册量、品牌对比、品牌排行或燃料月度查询。")
        params = args.get("parameters", {})
        extra = set(params) - QUERY_PARAMS[args["query_id"]]
        if extra:
            return _failure("unsupported_dimension", "此查询不支持这些参数；品牌与燃料不能交叉筛选。")
        required = ["start_month", "end_month"]
        if args["query_id"] == "brand_compare":
            required.append("makers")
        absent = [key for key in required if key not in params or params[key] in ("", [])]
        if absent:
            return _missing(absent, "请提供开始月份和结束月份（YYYY-MM）；品牌对比还需要品牌列表。")
        for key in ("start_month", "end_month"):
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", params[key]):
                return _failure("invalid_args", "月份必须采用 YYYY-MM 格式。")
        if params["start_month"] > params["end_month"]:
            return _failure("invalid_args", "开始月份不能晚于结束月份。")
        if "makers" in params and (not 2 <= len(params["makers"]) <= 8 or
                len({item.strip().casefold() for item in params["makers"]}) != len(params["makers"])):
            return _failure("invalid_args", "请选择 2 到 8 个不同品牌。")
        if "limit" in params and not 1 <= params["limit"] <= 30:
            return _failure("invalid_args", "排行 limit 必须为 1 到 30。")
    elif name == "literature.search":
        if not args.get("query", "").strip():
            return _missing(["query"], "请输入要检索的技术关键词，例如 constant current。")
        if not 1 <= len(args["query"].strip()) <= 200:
            return _failure("invalid_args", "检索关键词需为 1 到 200 个字符。")
        if not 1 <= args.get("limit", 5) <= 10:
            return _failure("invalid_args", "limit 必须为 1 到 10。")
    return None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_json(response):
    if response.headers.get_content_type() != "application/json":
        raise ValueError("Upstream returned a non-JSON content type")
    raw = response.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError("Upstream response exceeds size limit")
    value = json.loads(raw.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
    if not isinstance(value, dict):
        raise ValueError("Upstream JSON must be an object")
    return value


def _request(name, payload):
    # The endpoint is selected only by a registered tool name, never by input.
    body = None if name.endswith(".catalog") else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(ENDPOINTS[name], data=body, headers={"Accept": "application/json", "Content-Type": "application/json"})
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=NETWORK_TIMEOUT) as response:
        return _read_json(response)


def _require(value, condition, message):
    if not condition:
        raise ValueError(message)
    return value


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def _public_url(value):
    if not _text(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("https", "http") and bool(parsed.hostname) and not parsed.username and not parsed.password


def _same_parameter(key, actual, requested):
    if key in ("maker", "fuel") and isinstance(actual, str) and isinstance(requested, str):
        return actual.strip().casefold() == requested.strip().casefold()
    if key == "makers" and isinstance(actual, list) and isinstance(requested, list):
        return sorted(str(x).strip().casefold() for x in actual) == sorted(str(x).strip().casefold() for x in requested)
    return actual == requested


def _source(value):
    _require(value, isinstance(value, dict), "Missing source object")
    _require(value, all(_text(value.get(k)) for k in ("dataset", "version", "data_asof")), "Missing source dataset/version/data_asof")
    hashes = value.get("hashes")
    _require(hashes, isinstance(hashes, dict) and bool(hashes) and all(_hash(h) for h in hashes.values()), "Missing or invalid source hashes")


def _location(value):
    _require(value, isinstance(value, dict), "Missing original location")
    _require(value, all(k in value for k in ("kind", "section", "paragraph", "start_char", "end_char")), "Incomplete original location")
    _require(value, type(value["start_char"]) is int and type(value["end_char"]) is int and
             0 <= value["start_char"] < value["end_char"], "Invalid original offsets")


def _evidence(value, text):
    _require(value, isinstance(value, dict) and _text(value.get("quote")), "Missing evidence quotation")
    _require(value, value["quote"] in text, "Evidence quotation absent from returned original text")
    _require(value, type(value.get("start_char")) is int and type(value.get("end_char")) is int and
             0 <= value["start_char"] < value["end_char"], "Invalid evidence offsets")
    _require(value, text[value["start_char"]:value["end_char"]] == value["quote"], "Evidence offsets do not match the quotation")


def _validate_response(name, value, payload):
    if name.startswith("jpj."):
        _source(value.get("source"))
        if name == "jpj.catalog":
            _require(value, all(k in value for k in ("dataset", "version", "available_months", "makers", "fuels", "queries")), "Incomplete JPJ catalog")
        else:
            _require(value, value.get("query_id") == payload["query_id"], "Upstream query ID mismatch")
            _require(value, isinstance(value.get("parameters"), dict), "Missing executed parameters")
            _require(value, _validate_args(name, {"query_id": value["query_id"], "parameters": value["parameters"]}) is None,
                     "Executed parameters violate the query contract")
            for key, item in payload.get("parameters", {}).items():
                _require(value, _same_parameter(key, value["parameters"].get(key), item), "Executed parameters differ from request")
            _require(value, _text(value.get("sql")) and _text(value.get("metric_definition")), "Missing SQL or metric definition")
            columns, rows = value.get("columns"), value.get("rows")
            _require(value, isinstance(columns, list) and bool(columns) and all(_text(c) for c in columns), "Invalid result columns")
            _require(value, isinstance(rows, list) and all(isinstance(row, dict) and set(row) == set(columns) for row in rows), "Invalid result rows")
            _require(value, "registrations" in columns and all(type(row["registrations"]) is int and row["registrations"] >= 0 for row in rows), "Invalid registration counts")
    else:
        _require(value, _text(value.get("corpus_version")) and _text(value.get("method")), "Missing corpus version or method")
        key = "documents" if name.endswith("catalog") else "hits"
        items = value.get(key)
        _require(value, isinstance(items, list), "Missing document/hit list")
        if key == "hits":
            _require(value, len(items) <= payload.get("limit", 5), "Search returned too many hits")
        for item in items:
            _require(item, isinstance(item, dict) and all(_text(item.get(k)) for k in ("document_id", "title", "url")) and _hash(item.get("sha256")), "Incomplete source attribution")
            _require(item, _public_url(item["url"]), "Source URL must use HTTP or HTTPS")
            if key == "documents":
                _require(item, all(k in item for k in ("license", "split", "locations")), "Incomplete document provenance")
            else:
                _require(item, _text(item.get("text")), "Missing original text")
                _location(item.get("location"))
                _require(item, item["location"]["end_char"] - item["location"]["start_char"] == len(item["text"]), "Original location length does not match text")
                if "passage_sha256" in item:
                    _require(item, item["passage_sha256"] == hashlib.sha256(item["text"].encode("utf-8")).hexdigest(), "Passage hash does not match original text")
                for collection, fields in (("entities", ("type", "value")), ("relations", ("subject", "predicate", "object"))):
                    entries = item.get(collection)
                    _require(item, isinstance(entries, list), "Missing extraction list")
                    for entry in entries:
                        _require(entry, isinstance(entry, dict) and all(_text(entry.get(k)) for k in fields), "Invalid extracted assertion")
                        _evidence(entry.get("evidence"), item["text"])


def call_source(name, args):
    issue = _validate_args(name, args)
    if issue:
        return issue
    payload = dict(args)
    if name == "literature.search":
        payload.setdefault("limit", 5)
    try:
        value = _request(name, payload)
        _validate_response(name, value, payload)
    except HTTPError as exc:
        if 300 <= exc.code < 400:
            return _failure("upstream_redirect_denied", "本机服务返回重定向，已拒绝跟随。")
        if exc.code in (400, 422):
            try:
                error = _read_json(exc).get("error")
                if isinstance(error, dict) and _text(error.get("code")) and _text(error.get("message")):
                    return _failure("upstream_rejected", error["message"], upstream_error=error)
            except (ValueError, UnicodeError, OSError):
                pass
        return _failure("upstream_error", "本机服务返回错误。", upstream_status=exc.code)
    except (TimeoutError, socket.timeout):
        return _failure("timeout", "本机服务响应超时；没有生成查询结果。")
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return _failure("timeout", "本机服务响应超时；没有生成查询结果。")
        return _failure("service_unavailable", "本机数据服务不可用，请先启动对应项目。")
    except (ValueError, UnicodeError, OSError, TypeError) as exc:
        return _failure("invalid_upstream_response", "来源响应未通过契约或引用检查。", detail=str(exc)[:180])
    return {"ok": True, "executed": True, "result": value}


def register_tools(engine):
    for name in TOOLS:
        engine.register(name, lambda args, tool=name: call_source(tool, args), writes=False, timeout_s=6.0)
