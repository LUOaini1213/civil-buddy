//! Civil Buddy harness: Runtime · Tools · Memory · Eval · Trace.
//! Default production path is deterministic `steps`. LLM chat is explainer, not calculator.

use crate::config::Paths;
use crate::extract::facts_from_text;
use crate::packs::{self, ToolCtx};
use chrono::Local;
use serde_json::{json, Value};
use std::fs;
use uuid::Uuid;

pub const DEFAULT_MODE: &str = "steps";

const LEGAL_BID: &[&str] = &[
    "bid-parse__extract",
    "bid-compliance__gaps",
    "bid-tech__expand",
    "construction__scheme_draft",
];

#[derive(Clone, Debug)]
pub struct Ticket {
    pub session: String,
    pub project: String,
    pub jurisdiction: String,
    pub brief: String,
    pub path: String,
    pub confirm_ok: bool,
}

impl Ticket {
    pub fn from_args(session: &str, args: &Value) -> Self {
        let project = args
            .get("project_name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim();
        let brief = args
            .get("brief")
            .or_else(|| args.get("tender_text"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        Self {
            session: session.to_string(),
            project: if project.is_empty() {
                "未命名投标项目".into()
            } else {
                project.into()
            },
            jurisdiction: args
                .get("jurisdiction")
                .and_then(|v| v.as_str())
                .unwrap_or("SG")
                .into(),
            brief,
            path: args
                .get("path")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .into(),
            confirm_ok: args
                .get("confirm_ok")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        }
    }
}

#[derive(Clone, Debug)]
pub struct Step {
    pub name: String,
    pub tool: String,
    pub expert: String,
    pub legal: bool,
    pub ok: bool,
    pub note: String,
}

#[derive(Clone, Debug)]
pub struct Hitl {
    pub required: bool,
    pub confirmed: bool,
    pub pending: bool,
    pub gate: String,
}

pub struct Run {
    pub run_id: String,
    pub mode: String,
    pub session: String,
    pub project: String,
    pub jurisdiction: String,
    pub steps: Vec<Step>,
    pub files: Vec<Value>,
    pub notes: Vec<String>,
    pub hitl: Hitl,
    pub run_dir: std::path::PathBuf,
    pub job_dir: std::path::PathBuf,
    pub scores: Vec<String>,
    pub specials: Vec<String>,
    pub workheads: Vec<String>,
    pub envelope: Vec<String>,
    pub error: Option<String>,
}

impl Run {
    pub fn to_value(&self) -> Value {
        if let Some(e) = &self.error {
            return json!({"ok": false, "error": e, "run_id": self.run_id, "mode": self.mode});
        }
        json!({
            "ok": true,
            "harness": true,
            "mode": self.mode,
            "run_id": self.run_id,
            "project": self.project,
            "jurisdiction": self.jurisdiction,
            "notes": self.notes,
            "files": self.files,
            "job_dir": self.job_dir.to_string_lossy(),
            "run_dir": self.run_dir.to_string_lossy(),
            "scores": self.scores,
            "specials": self.specials,
            "workheads": self.workheads,
            "envelope": self.envelope,
            "hitl": {
                "required": self.hitl.required,
                "confirmed": self.hitl.confirmed,
                "pending": self.hitl.pending,
                "gate": self.hitl.gate,
            },
            "steps": self.steps.iter().map(|s| json!({
                "name": s.name,
                "tool": s.tool,
                "expert": s.expert,
                "legal": s.legal,
                "ok": s.ok,
                "note": s.note,
            })).collect::<Vec<_>>(),
            "illegal_tool_calls": self.illegal_count(),
        })
    }

    pub fn illegal_count(&self) -> usize {
        self.steps.iter().filter(|s| !s.legal).count()
    }
}

pub fn architecture() -> Value {
    json!({
        "product": "Civil Buddy",
        "kind": "application harness",
        "default_mode": DEFAULT_MODE,
        "thesis": "expert understands the user first; can chat or run; exclusive writes stay steps; tools own numbers",
        "layers": {
            "runtime": "understand → chat | run | both; run uses run_expert_steps; firm pack: run_bid_steps",
            "tools": "packs::execute whitelist; exclusive refuse; no invented unit prices or xyz",
            "memory": "session uploads + demo/out/<session>/runs/<run_id>/trace.json",
            "eval": "shadow_eval + shadow_eval_expert + GET /api/eval/live official pages",
            "trace": "ordered steps + run_dir",
            "hitl": "high-risk exclusive write only after 我明白，将由持证人员签认",
        },
        "modes": ["chat", "steps", "steps+talk"],
        "llm_role": "understand and talk; not calculator",
        "expert_runtime": "understand",
        "summoned_default": "chat",
        "intents": ["chat", "run", "both"],
    })
}

pub fn run_bid_steps(paths: &Paths, ticket: Ticket) -> Run {
    let run_id = format!(
        "{}-{}",
        Local::now().format("%H%M%S"),
        &Uuid::new_v4().simple().to_string()[..6]
    );
    let run_dir = paths
        .out_root
        .join(&ticket.session)
        .join("runs")
        .join(&run_id);
    let _ = fs::create_dir_all(&run_dir);
    let mut run = Run {
        run_id,
        mode: DEFAULT_MODE.into(),
        session: ticket.session.clone(),
        project: ticket.project.clone(),
        jurisdiction: ticket.jurisdiction.clone(),
        steps: vec![],
        files: vec![],
        notes: vec![],
        hitl: Hitl {
            required: false,
            confirmed: ticket.confirm_ok,
            pending: false,
            gate: "scheme".into(),
        },
        run_dir: run_dir.clone(),
        job_dir: paths.out_root.join(&ticket.session).join("firm"),
        scores: vec![],
        specials: vec![],
        workheads: vec![],
        envelope: vec![],
        error: None,
    };

    if !ticket.path.trim().is_empty() {
        match crate::attach::import_local(paths, &ticket.session, &ticket.path) {
            Ok(files) => {
                run.notes.push(format!("已导入本机 {} 个文件", files.len()));
                run.steps.push(Step {
                    name: "import".into(),
                    tool: "import_local".into(),
                    expert: "firm".into(),
                    legal: true,
                    ok: true,
                    note: format!("{} files", files.len()),
                });
            }
            Err(e) => {
                run.error = Some(e);
                persist_trace(&run);
                return run;
            }
        }
    }

    let mut source = ticket.brief.clone();
    for f in crate::attach::list_uploads(paths, &ticket.session) {
        if let Some(id) = f.get("id").and_then(|v| v.as_str()) {
            if let Ok(body) = crate::attach::read_upload(paths, &ticket.session, id, 0, 20_000) {
                source.push('\n');
                source.push_str(&body);
            }
        }
    }
    if source.trim().is_empty() {
        run.error = Some("没有招标正文。请导入本机文件、上传，或在说明里粘贴 ITT。".into());
        persist_trace(&run);
        return run;
    }

    let facts = facts_from_text(&source);
    run.scores = facts.scores.clone();
    run.specials = facts.specials.clone();
    run.workheads = facts.workheads.clone();
    run.envelope = facts.envelope.clone();
    run.hitl.required = !facts.specials.is_empty();
    run.hitl.pending = run.hitl.required && !ticket.confirm_ok;

    exec_step(
        &mut run,
        paths,
        "parse",
        "bid-parse",
        "bid",
        "low",
        true,
        "bid-parse__extract",
        &json!({
            "project_name": ticket.project,
            "jurisdiction": ticket.jurisdiction,
            "tender_text": source,
        }),
    );
    let mut required = Vec::new();
    for s in &facts.scores {
        required.push(format!("评分|{s}"));
    }
    for w in &facts.workheads {
        required.push(format!("workhead|{w}"));
    }
    for e in &facts.envelope {
        required.push(format!("信封|{e}"));
    }
    for s in &facts.specials {
        required.push(format!("专项|{s}"));
    }
    if required.is_empty() {
        required.push("评分|评标办法/评分点（原文未抽出，人工补）".into());
    }
    exec_step(
        &mut run,
        paths,
        "qa",
        "bid-compliance",
        "bid",
        "low",
        true,
        "bid-compliance__gaps",
        &json!({
            "required_items": required.join("\n"),
            "response_notes": ticket.brief,
            "jurisdiction": ticket.jurisdiction,
        }),
    );
    let scoring = if facts.scores.is_empty() {
        "评分点未在原文检出，目录只列待填".to_string()
    } else {
        facts.scores.join("\n")
    };
    exec_step(
        &mut run,
        paths,
        "outline",
        "bid-tech",
        "bid",
        "low",
        true,
        "bid-tech__expand",
        &json!({
            "project_name": ticket.project,
            "jurisdiction": ticket.jurisdiction,
            "scoring_points": scoring,
        }),
    );

    if run.hitl.required && ticket.confirm_ok {
        let scope = facts.specials.join("；");
        exec_step(
            &mut run,
            paths,
            "scheme",
            "construction",
            "construction",
            "high",
            true,
            "construction__scheme_draft",
            &json!({
                "project_name": ticket.project,
                "work_scope": scope,
                "known_facts": source.chars().take(4000).collect::<String>(),
                "jurisdiction": ticket.jurisdiction,
            }),
        );
    } else if run.hitl.pending {
        run.notes
            .push("HITL：专项/method statement 已抽出，未确认则不出施工草稿。".into());
        run.steps.push(Step {
            name: "scheme_gate".into(),
            tool: "construction__scheme_draft".into(),
            expert: "construction".into(),
            legal: true,
            ok: true,
            note: "pending HITL".into(),
        });
    }

    let firm_dir = run.job_dir.clone();
    let _ = fs::create_dir_all(&firm_dir);
    let price_path = firm_dir.join("价表-待填.md");
    let price_md = crate::firm::empty_price_md(&ticket.project, &ticket.jurisdiction, &facts);
    let price_ok = fs::write(&price_path, &price_md).is_ok();
    run.steps.push(Step {
        name: "price".into(),
        tool: "firm__price_sheet".into(),
        expert: "firm".into(),
        legal: true,
        ok: price_ok,
        note: "empty unit prices".into(),
    });
    if price_ok {
        run.files.push(json!({
            "expert": "firm",
            "name": "价表-待填.md",
            "path": price_path.to_string_lossy(),
        }));
    }

    let mut index = format!(
        "# {} · 一人公司成套投标作业单\n\nharness mode=`steps` · run_id={}\n\n内部讨论 AI 草稿，不是法定投标文件。缺的数字 [A001] / UNSPECIFIED。\n\n- 辖区：{}\n- HITL pending: {}\n- 会话：{}\n\n## Runtime 步骤\n\n",
        ticket.project, run.run_id, ticket.jurisdiction, run.hitl.pending, ticket.session
    );
    for s in &run.steps {
        index.push_str(&format!(
            "- {} · {} / {} · legal={} ok={}\n",
            s.name, s.expert, s.tool, s.legal, s.ok
        ));
    }
    index.push_str("\n## 已出稿\n\n");
    for f in &run.files {
        let name = f.get("name").and_then(|v| v.as_str()).unwrap_or("?");
        let path = f.get("path").and_then(|v| v.as_str()).unwrap_or("");
        index.push_str(&format!("- {name}\n  `{path}`\n"));
    }
    let index_path = firm_dir.join("成套作业单.md");
    if fs::write(&index_path, &index).is_ok() {
        run.files.push(json!({
            "expert": "firm",
            "name": "成套作业单.md",
            "path": index_path.to_string_lossy(),
        }));
    }
    persist_trace(&run);
    run
}

fn exec_step(
    run: &mut Run,
    paths: &Paths,
    name: &str,
    expert: &str,
    category: &str,
    risk: &str,
    confirm: bool,
    tool: &str,
    args: &Value,
) {
    let owner = crate::tier_map::exclusive_owner(tool);
    let legal = owner.map(|o| o == expert).unwrap_or(true) || LEGAL_BID.contains(&tool);
    let mut ctx = ToolCtx::new(
        paths.clone(),
        expert,
        category,
        risk,
        confirm,
        &run.session,
    );
    let out = packs::execute(&mut ctx, tool, args);
    let ok = out.contains("已写入");
    run.notes.push(format!("{name}: {out}"));
    run.files.extend(ctx.deliverables);
    run.steps.push(Step {
        name: name.into(),
        tool: tool.into(),
        expert: expert.into(),
        legal,
        ok,
        note: out.chars().take(160).collect(),
    });
}

fn persist_trace(run: &Run) {
    let _ = fs::create_dir_all(&run.run_dir);
    let _ = fs::write(run.run_dir.join("trace.json"), run.to_value().to_string());
}

/// Same ticket: steps path is source of truth. Policy sequence must be legal; core facts must appear.
pub fn shadow_eval(paths: &Paths, ticket: Ticket) -> Value {
    let run = run_bid_steps(paths, ticket);
    let illegal = run.illegal_count();
    let parse = run
        .files
        .iter()
        .find(|f| f.get("name").and_then(|v| v.as_str()) == Some("招标解析表.md"))
        .and_then(|f| f.get("path").and_then(|v| v.as_str()))
        .and_then(|p| fs::read_to_string(p).ok())
        .unwrap_or_default();
    let mut agreed = 0usize;
    let mut need = 0usize;
    for fact in run.scores.iter().chain(run.specials.iter()) {
        let key = fact.chars().take(12).collect::<String>();
        if key.trim().is_empty() {
            continue;
        }
        need += 1;
        if parse.contains(&key) || parse.contains(fact.as_str()) {
            agreed += 1;
        }
    }
    let agree_core = if need == 0 {
        parse.contains("招标解析")
    } else {
        agreed == need
    };
    let policy = ["bid-parse__extract", "bid-compliance__gaps", "bid-tech__expand"];
    let used: Vec<String> = run
        .steps
        .iter()
        .filter(|s| s.ok && LEGAL_BID.contains(&s.tool.as_str()))
        .map(|s| s.tool.clone())
        .collect();
    let policy_hit = policy.iter().all(|t| used.iter().any(|u| u == t));
    json!({
        "ok": run.error.is_none() && illegal == 0 && agree_core && policy_hit,
        "mode_a": "steps",
        "mode_b": "policy_sequence",
        "illegal_tool_calls": illegal,
        "agree_core": agree_core,
        "policy_hit": policy_hit,
        "need": need,
        "agreed": agreed,
        "run_id": run.run_id,
        "run_dir": run.run_dir.to_string_lossy(),
        "steps": run.steps.len(),
    })
}

pub fn fat_args(ticket: &Ticket, source: &str) -> Value {
    let src = if source.trim().is_empty() {
        ticket.brief.as_str()
    } else {
        source
    };
    let mut map = serde_json::Map::new();
    for (k, v) in [
        ("tender_text", src),
        ("text", src),
        ("brief", src),
        ("materials", src),
        ("work_scope", src),
        ("known_facts", src),
        ("items", src),
        ("item", src),
        ("notes", src),
        ("note", src),
        ("project_name", ticket.project.as_str()),
        ("jurisdiction", ticket.jurisdiction.as_str()),
        ("scoring_points", src),
        ("required_items", src),
        ("scope", src),
        ("systems", src),
        ("system", src),
        ("work_type", src),
        ("work_item", src),
        ("progress", src),
        ("event_facts", src),
        ("event", src),
        ("package", src),
        ("period", "2026-08"),
        ("material", src),
        ("inspection_lot", "lot-1"),
        ("scenario", src),
        ("site", ticket.project.as_str()),
        ("site_name", ticket.project.as_str()),
        ("discipline", src),
        ("issues", src),
        ("filters", src),
        ("level", src),
        ("window", src),
        ("trades", src),
        ("equipment", src),
        ("notice", src),
        ("role", src),
        ("contract_type", src),
        ("audience", src),
        ("topics", src),
        ("doc_type", src),
        ("subject", src),
        ("work_today", src),
        ("vendor", src),
        ("samples", src),
        ("rooms", src),
        ("span_note", src),
        ("method", src),
        ("corridor", src),
        ("stage", src),
        ("lod", "UNSPECIFIED"),
        ("users", src),
        ("open_items", src),
        ("description", src),
        ("task", src),
        ("response_notes", src),
    ] {
        map.insert(k.to_string(), Value::String(v.to_string()));
    }
    Value::Object(map)
}

pub fn run_expert_steps(paths: &Paths, expert: &crate::catalog::Expert, ticket: Ticket) -> Run {
    let run_id = format!(
        "e{}-{}",
        Local::now().format("%H%M%S"),
        &Uuid::new_v4().simple().to_string()[..6]
    );
    let run_dir = paths
        .out_root
        .join(&ticket.session)
        .join("runs")
        .join(&run_id);
    let _ = fs::create_dir_all(&run_dir);
    let mut run = Run {
        run_id,
        mode: DEFAULT_MODE.into(),
        session: ticket.session.clone(),
        project: ticket.project.clone(),
        jurisdiction: ticket.jurisdiction.clone(),
        steps: vec![],
        files: vec![],
        notes: vec![],
        hitl: Hitl {
            required: expert.risk == "high",
            confirmed: ticket.confirm_ok,
            pending: expert.risk == "high" && !ticket.confirm_ok,
            gate: "exclusive_write".into(),
        },
        run_dir: run_dir.clone(),
        job_dir: paths.out_root.join(&ticket.session).join(&expert.id),
        scores: vec![],
        specials: vec![],
        workheads: vec![],
        envelope: vec![],
        error: None,
    };

    if !ticket.path.trim().is_empty() {
        match crate::attach::import_local(paths, &ticket.session, &ticket.path) {
            Ok(files) => {
                run.notes.push(format!("已导入 {} 个文件", files.len()));
                run.steps.push(Step {
                    name: "import".into(),
                    tool: "import_local".into(),
                    expert: expert.id.clone(),
                    legal: true,
                    ok: true,
                    note: format!("{} files", files.len()),
                });
            }
            Err(e) => {
                run.error = Some(e);
                persist_trace(&run);
                return run;
            }
        }
    }

    let mut source = ticket.brief.clone();
    for f in crate::attach::list_uploads(paths, &ticket.session) {
        if let Some(id) = f.get("id").and_then(|v| v.as_str()) {
            if let Ok(body) = crate::attach::read_upload(paths, &ticket.session, id, 0, 20_000) {
                source.push('\n');
                source.push_str(&body);
            }
        }
    }
    if source.trim().is_empty() {
        source = format!("{} 作业", expert.name);
    }

    if run.hitl.pending {
        run.notes
            .push("HITL：高风险写盘需确认句「我明白，将由持证人员签认」。".into());
        run.steps.push(Step {
            name: "hitl_gate".into(),
            tool: crate::tier_map::expert_map(&expert.id)
                .and_then(|m| m.exclusive.first().cloned())
                .unwrap_or_default(),
            expert: expert.id.clone(),
            legal: true,
            ok: true,
            note: "pending HITL".into(),
        });
        persist_trace(&run);
        return run;
    }

    let args = fat_args(&ticket, &source);
    let exclusives = crate::tier_map::expert_map(&expert.id)
        .map(|m| m.exclusive.clone())
        .unwrap_or_default();
    let confirm = ticket.confirm_ok || expert.risk != "high";
    let mut ran = 0usize;
    for tool in exclusives {
        if tool.contains("fill_scheme") {
            continue;
        }
        exec_step(
            &mut run,
            paths,
            "exclusive",
            &expert.id,
            &expert.category,
            &expert.risk,
            confirm,
            &tool,
            &args,
        );
        ran += 1;
    }
    if ran == 0 {
        let md = format!(
            "# {} · 作业草稿\n\n本文件由 Civil Buddy 根据用户输入生成，仅供内部讨论与起草。不构成设计文件、法定专项施工方案、交底签认件、监理指令、专家论证材料或开工/竣工验收依据。\n\n- 专家：{}\n- 辖区：{}\n\n## 用户原文\n\n{}\n\n缺的数字 [A001] / UNSPECIFIED。\n",
            ticket.project, expert.name, ticket.jurisdiction, source
        );
        exec_step(
            &mut run,
            paths,
            "write",
            &expert.id,
            &expert.category,
            &expert.risk,
            confirm,
            "write_deliverable",
            &json!({
                "filename": format!("{}-作业草稿.md", expert.name),
                "markdown": md,
            }),
        );
    }
    persist_trace(&run);
    run
}

pub fn shadow_eval_expert(paths: &Paths, expert: &crate::catalog::Expert, ticket: Ticket) -> Value {
    let run = run_expert_steps(paths, expert, ticket);
    let illegal = run.illegal_count();
    let wrote = run.files.iter().any(|f| f.get("path").is_some());
    let ok = run.error.is_none()
        && illegal == 0
        && (wrote || run.hitl.pending);
    json!({
        "ok": ok,
        "expert": expert.id,
        "mode": "steps",
        "illegal_tool_calls": illegal,
        "wrote": wrote,
        "hitl_pending": run.hitl.pending,
        "run_id": run.run_id,
        "run_dir": run.run_dir.to_string_lossy(),
        "steps": run.steps.len(),
    })
}

pub fn load_trace(paths: &Paths, session: &str, run_id: &str) -> Option<Value> {
    let p = paths
        .out_root
        .join(session)
        .join("runs")
        .join(run_id)
        .join("trace.json");
    fs::read_to_string(p)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
}