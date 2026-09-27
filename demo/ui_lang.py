"""中文 | English for what the workbench server writes to the page.

The page says which language it shows (header X-Civil-Lang, else cookie cb_lang; demo/static/i18n.js sends both).
PageLanguage (a plain ASGI middleware) holds it for the request, reply_language.using_page_language holds it for a
turn's own thread, and then:

* reply_language.english_request() is true, so the notes the runtime writes itself (approval / sign-off, guards,
  link and question notes) are English, exactly as they already are for an English request;
* tr("中文 {name}", name=...) here picks the English wording for what this server writes (status lines, context
  notes, cancellations, fixed replies);
* an HTTP error's detail is looked up in the same table on the way out (localize()), so the raise sites stay as
  they are.

Nothing here changes what is routed, checked or approved: the sign-off sentences, the token gate and the
confirmation for one turn read the request, never the language. Draft bodies from the posts' templates, the posts'
knowledge and anything the model writes are not translated. A Chinese page (or none) gets exactly what it got
before: every function here returns its Chinese input unchanged unless the page language is English.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, Union

from packing_assistant.runtime.reply_language import normalize_language, page_language, using_page_language

HEADER = "x-civil-lang"
COOKIE = "cb_lang"
ROOT = Path(__file__).resolve().parents[1]

__all__ = ["HEADER", "COOKIE", "PageLanguage", "language_of", "english", "tr", "localize", "localize_route",
           "post_name", "page_language", "using_page_language"]


def language_of(headers: Iterable[Tuple[bytes, bytes]]) -> str:
    """"en" / "zh" / "" from raw ASGI headers: X-Civil-Lang first, then the cb_lang cookie."""
    header, cookie = "", ""
    for key, value in headers:
        name = key.decode("latin-1").lower()
        if name == HEADER:
            header = value.decode("latin-1")
        elif name == "cookie":
            for part in value.decode("latin-1").split(";"):
                k, _, v = part.strip().partition("=")
                if k == COOKIE:
                    cookie = v
    return normalize_language(header) or normalize_language(cookie)


class PageLanguage:
    """Pure ASGI (not BaseHTTPMiddleware): the context variable it sets is the one the endpoint, its thread pool and
    the exception handlers see."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        with using_page_language(language_of(scope.get("headers") or [])):
            await self.app(scope, receive, send)


def english() -> bool:
    return page_language() == "en"


# ---------------------------------------------------------------------------------------------------------------
# What this server writes, Chinese -> English. Exact messages first; PATTERNS catch the ones with a value inside.
EN: Dict[str, str] = {
    # demo/app.py
    "岗位能力契约不存在": "No capability contract for this post",
    "请选择有效岗位": "Choose a valid post",
    "协作运行记录不存在": "No collaboration run record",
    "无法保存附件，请检查工作台目录权限": "Cannot save the attachment; check the workbench folder permissions",
    "一次上传不能超过 25 MB": "One upload cannot exceed 25 MB",
    "单个附件不能超过 20 MB": "A single attachment cannot exceed 20 MB",
    "一次最多上传 12 个附件": "At most 12 attachments per upload",
    "上传表单字段过多": "Too many fields in the upload form",
    "上传内容格式无效，请重新选择文件后再试": "The upload is not in a valid format; choose the files again and retry",
    "录音不能超过 8 MB": "A recording cannot exceed 8 MB",
    "当前任务正在运行，请停止或等待完成后重新整理记忆": "The task is running; stop it or wait for it to finish, then rebuild the memory",
    "任务或原始资料不存在，无法重建；请核对当前任务的记录和附件":
        "The task or its source material does not exist, so nothing can be rebuilt; check this task's records and attachments",
    "当前模式或文件权限不允许重建；原始资料未改动": "The current mode or file permissions do not allow a rebuild; the source material is unchanged",
    "重建未完成，请检查存储空间或文件占用后重试；原始资料未改动":
        "The rebuild did not finish; check disk space or files in use and retry. The source material is unchanged",
    "来源范围须为 1–20000 个字符": "The source range must be 1–20000 characters",
    "该来源已失效，请重新检索": "This source is no longer valid; search again",
    "当前任务正在运行，请停止或等待完成后备份": "The task is running; stop it or wait for it to finish, then back it up",
    "备份包不能超过 128 MB": "A backup cannot be larger than 128 MB",
    "当前模式或目录权限不允许导入任务": "The current mode or folder permissions do not allow importing a task",
    "导入失败，请检查工作台目录空间和权限": "Import failed; check the workbench folder's space and permissions",
    "文件不存在": "File not found",
    "保存失败": "Save failed",
    "这个会话还没有事件记录": "This session has no event log yet",
    "run_id 无效": "Invalid run_id",
    "这轮没有可下载的文书": "This turn has no documents to download",
    "run 无效": "Invalid run",
    "file 无效": "Invalid file",
    "缺少 path 或 session/run/file": "Missing path or session/run/file",
    # demo/chat_service.py (prepare_turn and the turn)
    "会话 id 无效": "Invalid session id",
    "这个会话正在处理上一条消息，请完成或停止后重试": "This session is still handling the previous message; let it finish or stop it, then retry",
    "请输入消息": "Type a message",
    "消息过长，请把长资料作为附件上传": "The message is too long; upload long material as an attachment",
    "会话目录无效": "Invalid session folder",
    "请选择有效岗位，一次最多 8 岗": "Choose valid posts, at most 8 at a time",
    "箱单项目 id 无效": "Invalid packing-list project id",
    "施工计划项目 id 无效": "Invalid construction-plan project id",
    "一次对话只能绑定一个 CAD、施工计划或箱单项目": "One conversation can be bound to only one CAD, construction-plan or packing-list project",
    "无法读取所选施工计划，请重新打开项目后再试": "Cannot read the selected construction plan; reopen the project and retry",
    "无法读取所选箱单，请重新打开项目后再试": "Cannot read the selected packing list; reopen the project and retry",
    "项目不存在或已归档，请刷新项目列表": "The project does not exist or is archived; refresh the project list",
    "附件不存在，请重新选择当前会话的附件": "The attachment does not exist; select this session's attachments again",
    "资料用途只允许指定当前选择的附件": "Material roles can only be set for the attachments selected now",
    "本轮使用本地岗位工具；完整对话与任务记忆保存在本机。":
        "This turn uses the local post tools; the full conversation and task memory are kept on this machine.",
    " 本轮记忆或索引缓存未刷新，原始消息已保留。": " The memory or index cache for this turn was not refreshed; the original message is kept.",
    "识别任务并选择岗位": "Understanding the task and choosing posts",
    "物流箱单：核对原文、汇总并形成待确认建议": "Packing list: checking the source, summarising and preparing proposals to confirm",
    "施工计划：核对当前参数、形成待确认建议": "Construction plan: checking the current parameters and preparing proposals to confirm",
    "CAD 项目：检查图纸、执行受限工具": "CAD project: checking the drawing and running the restricted tools",
    "模型驱动：选岗、调工具、出稿": "Model-driven: choosing posts, calling tools, drafting",
    "建议编号无效": "Invalid proposal id",
    "施工计划建议已取消。": "The construction-plan proposal was cancelled.",
    "箱单建议已取消。": "The packing-list proposal was cancelled.",
    "CAD 项目保存已取消。": "Saving the CAD project was cancelled.",
    "\n\n模型与参数已保存到所选 CAD 项目。": "\n\nThe model and parameters were saved to the selected CAD project.",
    "完成": "done",
    "失败": "failed",
    "等待签认确认": "Waiting for sign-off",
    "本轮未执行写入": "Nothing was written in this turn",
    "本地用户": "local user",
    "已收到签认确认": "Sign-off received",
    "Civil Buddy 路由器": "Civil Buddy router",
    "招标协作": "Tender collaboration",
    "模型问答未完成": "The model answer did not finish",
    "模型未返回有效回答": "The model returned no valid answer",
    "\n\n本机找到以下相关原文，可展开来源核对。": "\n\nRelated source text found on this machine; expand the sources to check.",
    "问答": "Question",
    "未调用写入工具": "No write tool was called",
    "请先选择一个岗位，或用 @岗位名 说明需要的交付物，例如「@项目日报 写一份日报模板」。":
        "Choose a post first, or name the deliverable with @post, e.g. \"@pm-daily Draft a daily site report template\".",
    "本轮已取消": "This turn was cancelled",
    "页面断开后一直没有回来，本轮已取消": "The page disconnected and did not come back; this turn was cancelled",
    "页面断开超过时限，服务端自动停止；": "The page was away too long, so the server stopped it; ",
    "停止后续步骤；已完成文件保留": "Later steps stopped; finished files are kept",
    "本轮未完成，请检查模型设置或本地日志后重试。": "This turn did not finish; check the model settings or the local log and retry.",
    "本轮中断": "Turn interrupted",
    "会话未完整结束，可重试": "The session did not finish cleanly; you can retry",
    "\n\n[本轮中断，回答可能不完整]": "\n\n[This turn was interrupted; the answer may be incomplete]",
    "会话已释放": "The session was released",
    "按 {name} 工序起草": "Drafting with {name}'s steps",
    # demo/semantic_service.py (the context bar's semantic-summary note)
    "语义摘要未启用；使用规则记忆与检索。": "Semantic summary off; using rule memory and search.",
    "本轮无需模型问答；语义摘要不会参与业务字段或签认。":
        "No model answer needed this turn; a semantic summary never feeds business fields or sign-off.",
    "未配置模型，沿用本地规则记忆与检索。": "No model configured; using local rule memory and search.",
    "本轮更正优先，暂不加载旧语义摘要；使用当前原文与规则记忆。":
        "This turn's correction comes first: the old semantic summary is not loaded; using the current text and rule memory.",
    "相同资料的摘要暂缓重试；使用已有摘要、规则记忆与检索。":
        "The summary of the same material waits before retrying; using the existing summary, rule memory and search.",
    "正在整理较早对话的语义摘要，完整原文仍保留。": "Summarising the earlier conversation; the full source is kept.",
    "已生成部分历史的语义摘要；有原文依据，内容仍待核验。":
        "A semantic summary of part of the history was made; it is sourced but still to be verified.",
    "复用本任务已核对来源的语义摘要，内容仍待核验。": "Reusing this task's source-checked semantic summary; still to be verified.",
    "当前无需新增语义摘要；原文和规则记忆保留。": "No new semantic summary needed now; the source and rule memory are kept.",
    "本轮摘要已停止，迟到回复不会写入任务记忆。": "The summary for this turn was stopped; a late reply will not enter the task memory.",
    "语义摘要未生成或未通过校验，本轮沿用规则记忆与检索。":
        "The semantic summary was not made or failed its check; this turn uses rule memory and search.",
    " 原文链接展示最近 12 处，其余 {n} 处位置保留在摘要中。":
        " Source links show the latest 12 places; the other {n} stay recorded in the summary.",
    " 摘要因本轮输入预算未加入，原文可检索。": " The summary did not fit this turn's input budget; the source can be searched.",
    "摘要暂无可用条目或无法在预算内完整展示，本轮使用规则记忆与检索。":
        "The summary has no usable items or cannot be shown whole within the budget; this turn uses rule memory and search.",
    "本轮已停止，摘要未加入新的问答请求。": "This turn stopped; the summary was not added to a new question.",
    " 摘要未加入本轮问答，继续使用规则记忆与检索。": " The summary was not added to this turn's question; rule memory and search are used.",
    # demo/context.py (the context bar's note)
    "完整请求约 {used} / {usable} 输入 token，回复预留 {reserve}，窗口 {limit}。":
        "The full request is about {used} / {usable} input tokens, {reserve} reserved for the answer, window {limit}. ",
    "已压缩上下文：保留最近 {kept} 条原文，较早 {folded} 条仍可从本地检索找回。":
        "Context compacted: the latest {kept} messages kept verbatim, {folded} older ones can be found again by local search. ",
    "历史记忆因预算不足未加入。": "History memory left out for lack of budget. ",
    "{n} 条检索片段因预算不足未加入。": "{n} retrieved passages left out for lack of budget. ",
    "按本地编码保守估算，并非模型官方精确计数。": "A conservative local estimate, not the model's official count.",
    "{name} 尚未接入本地起草工具。可以先提问或完善该岗位的工具配置。":
        "{name} has no local drafting tool yet. Ask it questions first, or complete the post's tool setup.",
    # demo/uploads.py
    "session_id 无效：需 4–32 位 ASCII 字母、数字、连字符或下划线，不能以下划线开头":
        "Invalid session_id: 4–32 ASCII letters, digits, hyphens or underscores, not starting with an underscore",
    "附件会话目录不允许链接跳转": "The attachment session folder cannot be a link",
    "附件路径越界": "The attachment path is outside the session",
    "附件 id 无效": "Invalid attachment id",
    "附件不存在": "The attachment does not exist",
    "附件原件不存在": "The original attachment file does not exist",
    "附件文件不允许链接跳转": "An attachment file cannot be a link",
    "Office 文件解压后过大，请拆分后上传": "The Office file is too large once unpacked; split it and upload again",
    "暂不支持加密的 Office 文件": "Encrypted Office files are not supported yet",
    "Excel 文本解析依赖未安装：请安装 openpyxl": "The Excel reader is not installed: install openpyxl",
    "PDF 文本解析依赖未安装：请安装 pypdf；扫描件需先完成 OCR": "The PDF reader is not installed: install pypdf; scanned PDFs need OCR first",
    "暂不支持加密 PDF，请先解密后上传": "Encrypted PDFs are not supported yet; decrypt it first, then upload",
    "单文件不能超过 20 MB": "A single file cannot exceed 20 MB",
    "只接受 pdf / docx / xlsx / txt / md / csv / json / log": "Only pdf / docx / xlsx / txt / md / csv / json / log are accepted",
    "文件包含二进制内容，请上传有效的文本文件": "The file holds binary content; upload a valid text file",
    "没有收到文件": "No file received",
    "同一会话最多 12 个附件": "At most 12 attachments per session",
    "只能取 http / https 地址上的文件": "Only files at http / https addresses can be fetched",
    "地址里不能带用户名或密码": "The address cannot contain a user name or password",
    "域名解析失败": "The domain name could not be resolved",
    "拒绝访问本机或内网地址": "Addresses on this machine or the internal network are refused",
    "取不到这个地址上的文件": "Cannot fetch the file at this address",
    "重定向太多": "Too many redirects",
    "附件读取 offset 和 limit 必须为非负整数": "Attachment offset and limit must be non-negative integers",
    "附件不存在，请重新选择当前任务的附件": "The attachment does not exist; select this task's attachments again",
    # demo/model_settings.py and demo/context.py
    "Base URL 过长或包含空白、控制字符": "The base URL is too long or contains spaces or control characters",
    "Base URL 必须为完整 HTTP(S) 地址，不能含凭据、查询参数或片段":
        "The base URL must be a full HTTP(S) address without credentials, query or fragment",
    "模型名称需为 1–256 个字符，不能含空白或控制字符": "The model name must be 1–256 characters without spaces or control characters",
    "API Key 过长或包含空白、控制字符": "The API key is too long or contains spaces or control characters",
    "模型设置必须为 JSON 对象": "Model settings must be a JSON object",
    "clear 必须为布尔值": "clear must be a boolean",
    "semantic_summary 必须为布尔值": "semantic_summary must be a boolean",
    "更换 Base URL 需要重新填写 API Key（已存的 Key 不会发往新地址）":
        "Changing the base URL needs the API key again (the stored key is never sent to a new address)",
    "上下文设置必须为对象": "Context settings must be an object",
    "上下文窗口必须为 1024–2000000 的整数": "The context window must be an integer from 1024 to 2000000",
    "回复预留必须为至少 128 且小于上下文窗口的整数": "The answer reserve must be an integer of at least 128 and below the context window",
    "语义摘要开关必须为布尔值": "The semantic summary switch must be a boolean",
    # demo/projects.py, demo/workflow_service.py, demo/session_bundle.py, demo/turn_control.py
    "项目名不能为空": "The project name cannot be empty",
    "项目名含控制字符": "The project name contains control characters",
    "未归类是内置项目，不能改名或归档": "Unsorted is a built-in project; it cannot be renamed or archived",
    "项目不存在": "The project does not exist",
    "标题不能为空": "The title cannot be empty",
    "协作预算必须为对象": "The collaboration budget must be an object",
    "协作预算字段或数值无效": "Invalid collaboration budget field or value",
    "子任务窗口和输出预留不能超过模型设置": "The subtask window and output reserve cannot exceed the model settings",
    "当前任务尚无可备份记录": "This task has nothing to back up yet",
    "备份包超过 128 MB，请拆分任务": "The backup is over 128 MB; split the task",
    "不是 Civil Buddy 任务备份": "Not a Civil Buddy task backup",
    "备份包损坏或格式不完整": "The backup is damaged or incomplete",
    "当前为只读模式，不能导入任务": "Read-only mode: tasks cannot be imported",
    "子任务已停止": "The subtask was stopped",
    # demo/llm.py: what a model call that failed says (the error event and the audit line)
    "未配置 API Key，请在工作台「模型设置」中配置。": "No API key is configured; set one in \"Model settings\".",
    "模型流单条事件过大，已停止读取": "One event in the model stream was too large; reading stopped",
    "模型服务返回流错误，回复未完成，请重试": "The model service returned a stream error; the reply is incomplete, retry",
    "模型未返回可显示的文本，请检查模型设置后重试": "The model returned no text to show; check the model settings and retry",
    "模型流数据格式错误，回复未完成，请重试": "The model stream was malformed; the reply is incomplete, retry",
    "模型服务返回错误响应，回复未完成，请重试": "The model service returned an error; the reply is incomplete, retry",
    "模型流缺少有效回复数据，请检查接口兼容性": "The model stream had no valid reply data; check the API compatibility",
    "模型流回复结构无效，请检查接口兼容性": "The model stream reply had an invalid structure; check the API compatibility",
    "模型流文本格式无效，请检查接口兼容性": "The model stream text was invalid; check the API compatibility",
    "模型达到回复长度限制，内容未完成，请缩小问题后重试": "The model hit its reply length limit and did not finish; narrow the question and retry",
    "模型提前停止回复，内容未完成，请检查请求后重试": "The model stopped early and did not finish; check the request and retry",
    "模型连接已结束但未收到完成标记，回复可能不完整，请重试": "The model connection ended without a finish mark; the reply may be incomplete, retry",
    "模型返回了无效回复，请检查接口兼容性后重试": "The model returned an invalid reply; check the API compatibility and retry",
    "模型响应超时，请稍后重试": "The model timed out; retry later",
    "无法连接模型接口，请检查 Base URL 和网络后重试": "Cannot reach the model API; check the Base URL and the network, then retry",
    "模型响应超时，回复可能不完整，请重试": "The model timed out; the reply may be incomplete, retry",
    "模型连接异常，回复可能不完整，请检查网络后重试": "The model connection failed; the reply may be incomplete, check the network and retry",
    "模型输出预算必须为正整数": "The model output budget must be a positive integer",
}

_LLM_HINTS = {
    "认证失败，请检查 API Key 和接口权限": "authentication failed; check the API key and its permissions",
    "请求受限，请检查模型额度或稍后重试": "rate limited; check the model quota or retry later",
    "模型服务暂不可用，请稍后重试": "the model service is unavailable; retry later",
    "接口发生重定向，请检查 Base URL": "the API redirected; check the Base URL",
    "模型请求失败，请检查 Base URL 和模型名称": "the model request failed; check the Base URL and the model name",
}

#: (pattern on the Chinese text, English template or function of the match)
Replacement = Union[str, Callable[[re.Match], str]]
PATTERNS: Tuple[Tuple[re.Pattern, Replacement], ...] = ()


def _names(text: str) -> str:
    """A list of Chinese post names joined with 、 -> English names joined with commas."""
    return ", ".join(post_name(part.strip()) for part in re.split(r"[、,，]", text) if part.strip())


def _build_patterns() -> Tuple[Tuple[re.Pattern, Replacement], ...]:
    rows = [
        (r"项目名称最多 (\d+) 个字符", r"A project name has at most \1 characters"),
        (r"本机识别出错：(.+)", r"Local recognition failed: \1"),
        (r"备份失败：(.+)", r"Backup failed: \1"),
        (r"对方返回 (\d+)", r"The server answered \1"),
        (r"网址没有取到（(.+?)）：请下载后用「附件」上传。", r"The address could not be fetched (\1): download it and upload it with \"Attach\"."),
        (r"网址取回的文件没能保存，请检查工作台目录权限。", "The file fetched from the address could not be saved; check the workbench folder permissions."),
        (r"已从网址取回「(.+?)」并作为本轮附件。", r"Fetched \"\1\" from the address and attached it to this turn."),
        (r" 本轮资料超出预算，未加入：(.+?)(?: 等 (\d+) 项)?。",
         lambda m: " Over the budget for this turn, not included: " + m.group(1).replace("、", ", ")
         + (f" and more ({m.group(2)} in all)" if m.group(2) else "") + "."),
        (r" (\d+) 条较早原文由有来源的语义摘要替代，完整记录仍在本机。",
         r" \1 older messages were replaced by a sourced semantic summary; the full record stays on this machine."),
        (r"处理用户选中的 CAD 项目：(.+)", r"Working on the CAD project the user selected: \1"),
        (r"核对用户选中的施工计划：(.+?)；修改须在排程页确认", r"Checking the construction plan the user selected: \1; changes must be confirmed on the schedule page"),
        (r"核对用户选中的箱单：(.+?)；修改须在物流页确认", r"Checking the packing list the user selected: \1; changes must be confirmed on the logistics page"),
        (r"\n\n\[打开施工计划，核对并确认建议\]\((.+)\)", r"\n\n[Open the construction plan to check and confirm the proposal](\1)"),
        (r"\n\n\[打开箱单，核对并确认建议\]\((.+)\)", r"\n\n[Open the packing list to check and confirm the proposal](\1)"),
        (r"\n\n建议未登记，当前计划未修改：(.*)", r"\n\nThe proposal was not registered; the current plan is unchanged: \1"),
        (r"\n\n建议未登记，箱单未修改：(.*)", r"\n\nThe proposal was not registered; the packing list is unchanged: \1"),
        (r"\n\n模型预览计算已完成，但项目未保存：(.*)。请重新打开 CAD 项目后再试。",
         r"\n\nThe model preview was computed, but the project was not saved: \1. Reopen the CAD project and retry."),
        (r"任务未完成：(.*)", r"Task not finished: \1"),
        (r"LLM HTTP (\d+)：(.+)", lambda m: f"LLM HTTP {m.group(1)}: {_LLM_HINTS.get(m.group(2), m.group(2))}"),
        # a history source's title (demo/local_retrieval.py keeps it Chinese: it is part of the source's fingerprint)
        (r"(用户|助手) · 第 (\d+) 条消息", lambda m: f"{'User' if m.group(1) == '用户' else 'Assistant'} · message {m.group(2)}"),
        # the one-line summary the runtime writes after a draft (agent_loop / expert_turn); the draft itself stays Chinese
        (r"(.+?) 已出内部讨论草稿（(.+?)）。不可递交。(.*)",
         lambda m: f"{post_name(m.group(1))} produced an internal discussion draft ({m.group(2)}). Not for submission."
                   f"{m.group(3)}"),
        (r"本轮未写盘。(.*)", r"Nothing was written in this turn.\1"),
        (r"已按招标节选进矩阵。仍是 AI 草稿，submit_blocked=true，不可递交。(.*)",
         r"The tender excerpts were put into the matrix. Still an AI draft, submit_blocked=true, not for submission.\1"),
        (r"按 (.+) 工序起草", lambda m: f"Drafting with {post_name(m.group(1))}'s steps"),
        (r"(.+) 尚未接入本地起草工具。可以先提问或完善该岗位的工具配置。",
         lambda m: f"{post_name(m.group(1))} has no local drafting tool yet. Ask it questions first, or complete the post's tool setup."),
        (r"(.+?)。(箱单|施工计划)未修改，本轮建议未发布。",
         lambda m: f"{localize(m.group(1))}. The {'packing list' if m.group(2) == '箱单' else 'construction plan'} "
                   "was not changed; no proposal was published in this turn."),
        (r"\n\n\[(.+?)，已完成的文件保留下载。\]", lambda m: f"\n\n[{localize(m.group(1))}; finished files can still be downloaded.]"),
        (r"\n\n\[(.+?)，回答可能不完整。\]", lambda m: f"\n\n[{localize(m.group(1))}; the answer may be incomplete.]"),
        # the task router's reasons (packing_assistant/runtime/task_router.py)
        (r"尚未匹配明确岗位，可浏览岗位目录选择。", "No post matched clearly yet; browse the post list to choose one."),
        (r"按你已选择的岗位执行。", "Run with the posts you chose."),
        (r"这个岗位称呼有多个含义，请选择本次要处理的事项。", "This post name has more than one meaning; choose what to handle this time."),
        (r"按任务中明确点名的岗位执行。", "Run with the posts named in the task."),
        (r"招标与装柜联动：先读招标的物流条款，再按条款柜型用点名的装箱单真算，逐条写应答并记联动。",
         "Tender and packing link: read the tender's logistics clauses first, compute with the named packing list on the "
         "container type they set, answer clause by clause and record the link."),
        (r"综合投标响应检查需要先解析原文，再分别整理技术响应和检查缺口，最后汇总。",
         "A combined bid response check reads the source first, then organises the technical response and checks the "
         "gaps separately, and summarises last."),
        (r"任务同时对应不同职责，请明确要技术会审还是变更签证等具体交付。",
         "The task fits different responsibilities; say which deliverable you need, e.g. a drawing review or a variation."),
        (r"根据任务中的具体交付和专业词选用：(.+)。", lambda m: f"Chosen from the deliverable and trade terms in the task: {_names(m.group(1))}."),
        (r"涉及岗位较多，请先选择本轮的主要交付。", "Many posts are involved; choose the main deliverable for this turn first."),
        (r"处理图纸会审、专业接口与设计变更技术事项", "Drawing review, discipline interfaces and design-change technical matters"),
        (r"整理变更签证的事实、依据与工程量栏", "Facts, basis and quantity columns of a variation / site instruction"),
        (r"解析招标原文", "Read the tender source"),
        (r"整理技术响应", "Organise the technical response"),
        (r"检查响应缺口", "Check the response gaps"),
        (r"汇总证据与未解决事项", "Summarise the evidence and open items"),
    ]
    return tuple((re.compile("^" + pattern + "$", re.S), repl) for pattern, repl in rows)


@lru_cache(maxsize=1)
def _posts() -> Dict[str, Dict[str, str]]:
    """id -> {"zh": Chinese name, "name": English, "title": English} for the built-in posts."""
    try:
        seed = json.loads((ROOT / "workbench" / "seed.json").read_text(encoding="utf-8"))
        english_map = json.loads((ROOT / "workbench" / "posts_en.json").read_text(encoding="utf-8"))["posts"]
    except (OSError, ValueError, KeyError):
        return {}
    out = {}
    for expert in seed.get("experts", []):
        row = english_map.get(expert["id"]) or {}
        out[expert["id"]] = {"zh": expert.get("name", ""), "name": row.get("name", ""), "title": row.get("title", "")}
    return out


def post_name(value: Any, *, force: bool = False) -> str:
    """English name of a post (given its id, its Chinese name or an object with .id/.name) when the page is English;
    otherwise, and for a post made in the studio, its own name."""
    ident = getattr(value, "id", None) if not isinstance(value, (str, dict)) else (value.get("id") if isinstance(value, dict) else value)
    own = getattr(value, "name", None) if not isinstance(value, (str, dict)) else (value.get("name") if isinstance(value, dict) else value)
    if not (force or english()):
        return str(own or ident or "")
    posts = _posts()
    row = posts.get(str(ident or "")) or next((r for r in posts.values() if r["zh"] and r["zh"] == own), None)
    return (row or {}).get("name") or str(own or ident or "")


def tr(message: str, **values: Any) -> str:
    """``message`` (Chinese, with {name} fields) in the page's language, fields filled."""
    text = EN.get(message, message) if english() else message
    return text.format(**values) if values else text


def localize(text: Any) -> Any:
    """A finished Chinese message this server (or the router) wrote, in English when the page is English: an exact
    entry, else a pattern with its values carried over, else the text as it was."""
    if not english() or not isinstance(text, str) or not text:
        return text
    if text in EN:
        return EN[text]
    global PATTERNS
    if not PATTERNS:
        PATTERNS = _build_patterns()
    for pattern, repl in PATTERNS:
        m = pattern.match(text)
        if m:
            return repl(m) if callable(repl) else m.expand(repl)
    return text


def localize_route(route: Optional[dict]) -> Optional[dict]:
    """The route as the page shows it: reason, candidate labels and step labels in English when the page is. The ids
    it routes on are untouched (a copy is returned)."""
    if not english() or not isinstance(route, dict):
        return route
    posts = _posts()
    out = dict(route)
    out["reason"] = localize(route.get("reason"))
    candidates = []
    for c in route.get("candidates") or []:
        c = dict(c)
        eid = (c.get("expert_ids") or [""])[0]
        c["label"] = post_name(eid) if eid in posts else c.get("label")
        reason = localize(c.get("reason"))
        if reason == c.get("reason") and eid in posts and posts[eid]["title"]:
            reason = posts[eid]["title"]
        c["reason"] = reason
        candidates.append(c)
    if "candidates" in route:
        out["candidates"] = candidates
    steps = []
    for s in route.get("steps") or []:
        s = dict(s)
        label = localize(s.get("label"))
        if label == s.get("label") and s.get("expert_id") in posts:
            label = post_name(s["expert_id"])
        s["label"] = label
        steps.append(s)
    if "steps" in route:
        out["steps"] = steps
    return out
