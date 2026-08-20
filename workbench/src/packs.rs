//! Three-tier tools: 通用 / 大类共享 / 专家独有.
//! Visibility is resolved by expert_id (see `tier_map`). Execute refuses exclusives
//! called under the wrong expert.

use crate::catalog::seed;
use crate::config::Paths;
use crate::tier_map;
use crate::rag::{list_kb, read_kb, search_kb};
use chrono::Local;
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

const DISCLAIMER: &str = "本文件由 Civil Buddy 根据用户输入生成，仅供内部讨论与起草。不构成设计文件、法定专项施工方案、交底签认件、监理指令、专家论证材料或开工/竣工验收依据。涉及结构安全、基坑、临边与洞口、高处作业、脚手架、模板支撑、起重、有限空间、交通导改、验收的内容，必须由具备相应资格的人员依据正式规范文本复核并签字后方可实施。";

#[derive(Clone, Debug)]
pub struct ToolDef {
    pub name: &'static str,
    pub description: &'static str,
    pub parameters: Value,
}

impl ToolDef {
    pub fn openai_tool(&self) -> Value {
        json!({
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        })
    }

    pub fn mcp_tool(&self) -> Value {
        json!({
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters,
        })
    }
}

pub struct ToolCtx {
    pub paths: Paths,
    pub expert_id: String,
    pub category: String,
    pub risk: String,
    pub confirm_ok: bool,
    pub session_id: String,
    pub out_dir: PathBuf,
    pub citations: Vec<Value>,
    pub deliverables: Vec<Value>,
}

impl ToolCtx {
    pub fn new(paths: Paths, expert_id: &str, category: &str, risk: &str, confirm_ok: bool, session_id: &str) -> Self {
        let out_dir = paths.out_root.join(session_id).join(expert_id);
        let _ = fs::create_dir_all(&out_dir);
        Self {
            paths,
            expert_id: expert_id.to_string(),
            category: category.to_string(),
            risk: risk.to_string(),
            confirm_ok,
            session_id: session_id.to_string(),
            out_dir,
            citations: vec![],
            deliverables: vec![],
        }
    }

    fn gate(&self) -> Result<(), String> {
        if self.risk == "high" && !self.confirm_ok {
            return Err("拒绝写盘：高风险稿需要用户确认句「我明白，将由持证人员签认」。".into());
        }
        Ok(())
    }

    fn write_md(&mut self, filename: &str, markdown: &str) -> Result<String, String> {
        self.gate()?;
        let mut name = Path::new(filename)
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("draft.md")
            .to_string();
        if !(name.ends_with(".md") || name.ends_with(".txt") || name.ends_with(".docx")) {
            name.push_str(".md");
        }
        let path = self.out_dir.join(&name);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let hits = forbidden_hits(markdown);
        if !hits.is_empty() {
            return Err(format!(
                "拒绝写盘：成稿检出法定断言或辖区混用：{}",
                hits.join("、")
            ));
        }
        fs::write(&path, markdown).map_err(|e| e.to_string())?;
        let item = json!({
            "expert": self.expert_id,
            "name": name,
            "path": path.to_string_lossy(),
        });
        self.deliverables.push(item);
        Ok(format!("已写入 {}", path.display()))
    }
}

pub fn default_expert(pack: &str) -> &'static str {
    match pack {
        "bid" => "bid-parse",
        "design" => "architecture",
        "bim" => "bim-coord",
        "planning" => "plan-master",
        "construction" => "construction",
        "hse" => "safety-brief",
        "commercial" => "cost",
        "procurement" => "proc-plan",
        "plant" => "equip",
        "lab" => "lab-mix",
        "finance" => "finance-book",
        "docs" => "supervision",
        "hr" => "hr-recruit",
        "admin" => "admin-doc",
        "it" => "it-ops",
        "people" => "worker-brief",
        _ => "construction",
    }
}

pub fn valid_pack(pack: &str) -> bool {
    seed().categories.iter().any(|c| c.id == pack)
}

fn obj(props: Value, required: &[&str]) -> Value {
    json!({
        "type": "object",
        "properties": props,
        "required": required,
    })
}

fn core_tools() -> Vec<ToolDef> {
    vec![
        ToolDef {
            name: "search_kb",
            description: "检索本专家库、本大类共享库、公司硬规则。先检索再写正文。",
            parameters: obj(json!({"query": {"type": "string"}, "expert_id": {"type": "string"}}), &["query"]),
        },
        ToolDef {
            name: "read_kb",
            description: "按相对路径阅读一条知识库全文，路径来自 search_kb 或 list_kb。",
            parameters: obj(json!({"path": {"type": "string"}}), &["path"]),
        },
        ToolDef {
            name: "list_kb",
            description: "列出本专家可见的全部知识文件（专家私库 + 大类共享 + 公司）。",
            parameters: obj(json!({"expert_id": {"type": "string"}}), &[]),
        },
        ToolDef {
            name: "write_deliverable",
            description: "把独立完成的成稿落到本会话交付目录。高风险稿须用户已确认。",
            parameters: obj(
                json!({
                    "filename": {"type": "string", "description": "如 专项方案-AI草稿.md"},
                    "markdown": {"type": "string"}
                }),
                &["filename", "markdown"],
            ),
        },
        ToolDef {
            name: "web_search",
            description: "现场联网检索现行口径。摘要不是条文；优先官方门户（.gov.sg / BCA / MOM / SCDF / PUB / LTA / IRAS / GeBIZ / SSO / 发改委 / 住建）。条款号没打开原文就 unverified。",
            parameters: obj(json!({"query": {"type": "string"}}), &["query"]),
        },
        ToolDef {
            name: "web_open",
            description: "打开一条 https 官方页，抽取可见文字。不要打开本机/内网。PDF 请让用户上传。",
            parameters: obj(json!({"url": {"type": "string"}}), &["url"]),
        },
        ToolDef {
            name: "list_attachments",
            description: "列出用户本会话上传的招标/规范/表格。先看这个再猜用户有没有传文件。",
            parameters: obj(json!({}), &[]),
        },
        ToolDef {
            name: "read_attachment",
            description: "阅读用户上传附件的抽出文字。id 来自 list_attachments。",
            parameters: obj(
                json!({
                    "id": {"type": "string"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"}
                }),
                &["id"],
            ),
        },
        ToolDef {
            name: "import_local",
            description: "按用户给出的本机完整路径导入招标/规范（文件或文件夹）。禁止把 D:\\layout 当缺省作业根。",
            parameters: obj(json!({"path": {"type": "string"}}), &["path"]),
        },
        ToolDef {
            name: "firm__bid_pack",
            description: "一人公司成套投标（易标序）：读本机/附件 → 招标解析 → 废标缺口 → 技术标目录 → 作业单。有专项且已确认才出施工草稿。",
            parameters: obj(
                json!({
                    "project_name": {"type": "string"},
                    "jurisdiction": {"type": "string"},
                    "path": {"type": "string"},
                    "brief": {"type": "string"},
                    "tender_text": {"type": "string"},
                    "confirm_ok": {"type": "boolean"}
                }),
                &[],
            ),
        },
    ]
}

fn pack_tools(pack: &str) -> Vec<ToolDef> {
    match pack {
        "bid" => vec![
            ToolDef {
                name: "bid__scan_forbidden",
                description: "投标大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "bid-parse__extract",
                description: "招标解析独有：从招标文本抽出评分点、资质、工期、必须编制的专项。默认 SG。",
                parameters: obj(
                    json!({
                        "tender_text": {"type": "string"},
                        "project_name": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["tender_text"],
                ),
            },
            ToolDef {
                name: "bid-compliance__gaps",
                description: "废标检查独有：对照必须响应项列出未响应/易废标缺口。",
                parameters: obj(
                    json!({
                        "required_items": {"type": "string", "description": "招标要求，换行或分号分隔"},
                        "response_notes": {"type": "string", "description": "拟响应或已有材料说明"}
                    }),
                    &["required_items"],
                ),
            },
            ToolDef {
                name: "bid-tech__expand",
                description: "技术标独有：按评分点生成技术标目录草稿。条款未抽原文则 UNSPECIFIED。",
                parameters: obj(
                    json!({
                        "scoring_points": {"type": "string"},
                        "project_name": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scoring_points"],
                ),
            },
        ],
        "construction" => vec![
            ToolDef {
                name: "construction__scan_forbidden",
                description: "施工大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "construction__scheme_draft",
                description: "施工方案独有：按 11 章写出专项方案讨论提纲。默认新加坡工地 SG；无 SS/CP/BCA/WSH 原文则 UNSPECIFIED / [A001]。",
                parameters: obj(
                    json!({
                        "project_name": {"type": "string"},
                        "work_scope": {"type": "string"},
                        "jurisdiction": {"type": "string", "description": "默认 SG；可 CN / SG / EU / DUAL"},
                        "known_facts": {"type": "string"},
                        "unknowns": {"type": "string"},
                        "site_name": {"type": "string", "description": "工地名称，如 Tuas / Jurong 工地"}
                    }),
                    &["project_name", "work_scope"],
                ),
            },
            ToolDef {
                name: "construction__fill_scheme_docx",
                description: "施工方案独有：用已有 draft 填模板产出 docx。辖区默认 SG。",
                parameters: obj(
                    json!({
                        "draft_filename": {"type": "string"},
                        "project_name": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["project_name"],
                ),
            },
            ToolDef {
                name: "method-hazard__judge_hazard",
                description: "危大识别独有：只判定、不签发。缺尺寸则信息不足。",
                parameters: obj(
                    json!({
                        "work_type": {"type": "string"},
                        "height_m": {"type": "number"},
                        "excavation_depth_m": {"type": "number"},
                        "description": {"type": "string"},
                        "jurisdiction": {"type": "string", "description": "默认 SG"}
                    }),
                    &["work_type"],
                ),
            },
            ToolDef {
                name: "survey__record",
                description: "测量独有：控制网/放样记录口径。无用户坐标不编点号。默认 SG。",
                parameters: obj(
                    json!({
                        "work_item": {"type": "string"},
                        "known_points": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["work_item"],
                ),
            },
            ToolDef {
                name: "dispatch__daily",
                description: "生产调度独有：调度日报草稿。不编进度百分比。",
                parameters: obj(
                    json!({
                        "progress": {"type": "string"},
                        "issues": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["progress"],
                ),
            },
        ],
        "commercial" => vec![
            ToolDef {
                name: "commercial__scan_forbidden",
                description: "商务大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "cost__takeoff",
                description: "造价独有：工程量拆分表。无清单则单价/合价写 TBD，禁止编综合单价。",
                parameters: obj(
                    json!({
                        "project_name": {"type": "string"},
                        "items": {"type": "string", "description": "分项，换行；可含数量单位"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["items"],
                ),
            },
            ToolDef {
                name: "variation__form",
                description: "变更签证独有：事实、依据、工程量栏，金额待填。",
                parameters: obj(
                    json!({
                        "event_facts": {"type": "string"},
                        "basis": {"type": "string"},
                        "qty_note": {"type": "string"}
                    }),
                    &["event_facts"],
                ),
            },
            ToolDef {
                name: "claim__notice",
                description: "索赔独有：事件、证据、时限，不编金额。",
                parameters: obj(
                    json!({
                        "event": {"type": "string"},
                        "evidence": {"type": "string"},
                        "deadline_note": {"type": "string"}
                    }),
                    &["event"],
                ),
            },
            ToolDef {
                name: "subcontract__sheet",
                description: "分包结算独有：验工/扣款表头。无业主确认不编金额。",
                parameters: obj(
                    json!({
                        "package": {"type": "string"},
                        "qty_note": {"type": "string"}
                    }),
                    &["package"],
                ),
            },
            ToolDef {
                name: "interim__measure",
                description: "验工计价独有：对上验工表头。无业主确认不编金额。",
                parameters: obj(
                    json!({
                        "period": {"type": "string"},
                        "qty_note": {"type": "string"}
                    }),
                    &["period"],
                ),
            },
        ],
        "lab" => vec![
            ToolDef {
                name: "lab__scan_forbidden",
                description: "试验大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "lab-mix__report",
                description: "配合比独有：四层目录。无试验数据则施工配比整节待填。",
                parameters: obj(
                    json!({
                        "material": {"type": "string"},
                        "has_trial_data": {"type": "boolean"},
                        "notes": {"type": "string"}
                    }),
                    &["material"],
                ),
            },
            ToolDef {
                name: "lab-sample__list",
                description: "见证取样独有：类别|部位|见证人空|升级路径。组数 [A001]。",
                parameters: obj(
                    json!({
                        "materials": {"type": "string"},
                        "lot_notes": {"type": "string"}
                    }),
                    &["materials"],
                ),
            },
            ToolDef {
                name: "lab-record__ledger",
                description: "试验台账独有：报告编号待核|仪器检定|结论待填。",
                parameters: obj(json!({"samples": {"type": "string"}}), &["samples"]),
            },
        ],
        "hse" => vec![
            ToolDef {
                name: "hse__scan_forbidden",
                description: "安质环大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "safety-brief__talk",
                description: "安全交底独有：11 栏。毫米/电话 [A001]。确认句后才写盘。",
                parameters: obj(
                    json!({
                        "work_item": {"type": "string"},
                        "hazards": {"type": "string"},
                        "controls": {"type": "string"}
                    }),
                    &["work_item"],
                ),
            },
            ToolDef {
                name: "quality__lot",
                description: "质量独有：主控|一般|隐蔽三表，结果=未检。",
                parameters: obj(
                    json!({
                        "inspection_lot": {"type": "string"},
                        "items": {"type": "string"}
                    }),
                    &["inspection_lot"],
                ),
            },
            ToolDef {
                name: "emergency__plan",
                description: "应急独有：综合目录+点名专项+演练表头。电话医院待填。",
                parameters: obj(
                    json!({
                        "scenario": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scenario"],
                ),
            },
            ToolDef {
                name: "env__list",
                description: "环保独有：扬尘/弃土/污水/夜间/市容五行，限值 UNSPECIFIED。",
                parameters: obj(
                    json!({
                        "site": {"type": "string"},
                        "issues": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["site"],
                ),
            },
        ],
        "design" => vec![
            ToolDef {
                name: "design__scan_forbidden",
                description: "设计大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "architecture__memo",
                description: "建筑独有：专业说明/提纲。无计算书输入不定量。",
                parameters: obj(
                    json!({
                        "discipline": {"type": "string"},
                        "scope": {"type": "string"},
                        "open_items": {"type": "string"}
                    }),
                    &["discipline", "scope"],
                ),
            },
            ToolDef {
                name: "structure__calc_outline",
                description: "结构独有：计算书提纲。无荷载/材料不定量。",
                parameters: obj(
                    json!({
                        "system": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["system"],
                ),
            },
            ToolDef {
                name: "geotech__brief",
                description: "岩土独有：勘察/地基提纲。无地勘不填承载力。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "known_facts": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "plumbing__memo",
                description: "给排水独有：系统原则。无标高/水压不编管径。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "hvac__memo",
                description: "暖通独有：空调/通风/防排烟原则。无负荷不定机型。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "electrical__memo",
                description: "电气独有：供配电/照明/防雷原则。无负荷不选变压器。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "fire-protect__brief",
                description: "消防独有：专篇提纲。不替代审图，不编喷淋强度。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "systems": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "steel__memo",
                description: "钢结构独有：体系/连接提纲。无荷载不定量。",
                parameters: obj(
                    json!({
                        "system": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["system"],
                ),
            },
            ToolDef {
                name: "landscape__memo",
                description: "景观独有：种植/铺装原则。无苗木表不编规格。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "interior__schedule",
                description: "室内独有：房间界面表。无样板不编品牌。",
                parameters: obj(
                    json!({
                        "rooms": {"type": "string"},
                        "finishes": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["rooms"],
                ),
            },
            ToolDef {
                name: "facade__brief",
                description: "幕墙独有：体系/预埋原则。无风压不定量。",
                parameters: obj(
                    json!({
                        "system": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["system"],
                ),
            },
            ToolDef {
                name: "intel-weak__memo",
                description: "弱电独有：系统清单提纲。不编点数和品牌。",
                parameters: obj(
                    json!({
                        "systems": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["systems"],
                ),
            },
            ToolDef {
                name: "civil-defense__brief",
                description: "人防/掩蔽所独有：专篇提纲。不替代审图。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "hydraulic__outline",
                description: "水利独有：堤防/水闸提纲。无水文不定量。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "port__outline",
                description: "港航独有：码头/泊位提纲。无水位波浪不定量。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "municipal__memo",
                description: "市政道路独有：横断面原则。无红线不定量。",
                parameters: obj(
                    json!({
                        "scope": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["scope"],
                ),
            },
            ToolDef {
                name: "bridge__outline",
                description: "桥梁独有：桥型提纲。无跨径地质不定量。",
                parameters: obj(
                    json!({
                        "span_note": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["span_note"],
                ),
            },
            ToolDef {
                name: "tunnel__outline",
                description: "隧道独有：工法比选提纲。无地质不定支护。",
                parameters: obj(
                    json!({
                        "method": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["method"],
                ),
            },
            ToolDef {
                name: "traffic__skeleton",
                description: "交通独有：影响评价报告骨架。不编流量。",
                parameters: obj(
                    json!({
                        "corridor": {"type": "string"},
                        "open_items": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["corridor"],
                ),
            },
            ToolDef {
                name: "design-coord__minutes",
                description: "设计协调独有：会审纪要。不改图。",
                parameters: obj(
                    json!({
                        "issues": {"type": "string"},
                        "attendees": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["issues"],
                ),
            },
        ],
        "bim" => vec![
            ToolDef {
                name: "bim__scan_forbidden",
                description: "BIM 大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "bim-coord__clash",
                description: "碰撞/协调纪要骨架。",
                parameters: obj(
                    json!({
                        "disciplines": {"type": "string"},
                        "issues": {"type": "string"}
                    }),
                    &["issues"],
                ),
            },
            ToolDef {
                name: "bim-qto__rules",
                description: "模型算量口径。不编单价。",
                parameters: obj(json!({"filters": {"type": "string"}}), &["filters"]),
            },
            ToolDef {
                name: "bim-deliver__lod",
                description: "交付独有：阶段/细度/格式清单。不宣称已具备报审条件。",
                parameters: obj(
                    json!({
                        "stage": {"type": "string"},
                        "lod": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["stage"],
                ),
            },
        ],
        "planning" => vec![
            ToolDef {
                name: "planning__scan_forbidden",
                description: "计划大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
            name: "plan-master__network",
            description: "总控/周月计划骨架。无定额不编用量。",
            parameters: obj(
                json!({
                    "level": {"type": "string", "description": "master / lookahead / resource"},
                    "milestones": {"type": "string"}
                }),
                &["level"],
            ),
        },
            ToolDef {
                name: "plan-lookahead__week",
                description: "周月计划独有：四周滚动表。制约未清不得写入本周承诺。",
                parameters: obj(
                    json!({
                        "window": {"type": "string"},
                        "constraints": {"type": "string"},
                        "works": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["window"],
                ),
            },
            ToolDef {
                name: "plan-resource__peak",
                description: "资源独有：劳动力|机具|材料三表。无定额不编工日台班，数量待填。",
                parameters: obj(
                    json!({
                        "trades": {"type": "string"},
                        "window": {"type": "string"},
                        "equipment": {"type": "string"},
                        "items": {"type": "string"},
                        "material": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["trades"],
                ),
            },
        ],
        "procurement" => vec![
            ToolDef {
                name: "procurement__scan_forbidden",
                description: "采购大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "proc-compare__table",
                description: "比价表。无报价不编价。",
                parameters: obj(
                    json!({
                        "item": {"type": "string"},
                        "vendors": {"type": "string"}
                    }),
                    &["item"],
                ),
            },
            ToolDef {
                name: "proc-plan__schedule",
                description: "采购计划表：甲指/自采、提前期。",
                parameters: obj(json!({"items": {"type": "string"}}), &["items"]),
            },
            ToolDef {
                name: "proc-vendor__eval",
                description: "供方独有：评价表头。不编分数和中标结论。",
                parameters: obj(
                    json!({
                        "vendor": {"type": "string"},
                        "criteria": {"type": "string"}
                    }),
                    &["vendor"],
                ),
            },
        ],
        "plant" => vec![
            ToolDef {
                name: "plant__scan_forbidden",
                description: "物机大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "equip__ledger",
                description: "设备台账独有：只抄用户设备名与已给证件。无证件不编进场结论。",
                parameters: obj(
                    json!({
                        "equipment": {"type": "string"},
                        "certs": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["equipment"],
                ),
            },
            ToolDef {
                name: "warehouse__log",
                description: "仓管独有：按行抄收发原文。有数只抄、无数 TBD。无盘点不编盈亏。",
                parameters: obj(
                    json!({
                        "item": {"type": "string"},
                        "note": {"type": "string"},
                        "jurisdiction": {"type": "string"}
                    }),
                    &["item"],
                ),
            },
            ToolDef {
                name: "pack-ship__list",
                description: "装箱拼柜独有：列出 list / plan / export。不含数字。",
                parameters: obj(json!({}), &[]),
            },
            ToolDef {
                name: "pack-ship__plan",
                description: "装箱拼柜独有：出作业单。柜数/坐标只抄 packing-agent 工具回传，否则 UNSPECIFIED。不编 xyz。",
                parameters: obj(
                    json!({
                        "materials": {"type": "string"},
                        "project_name": {"type": "string"},
                        "jurisdiction": {"type": "string"},
                        "notes": {"type": "string"}
                    }),
                    &["materials"],
                ),
            },
            ToolDef {
                name: "pack-ship__export",
                description: "装箱拼柜独有：导出证据。utilization/can_fit/mid50/系固待办只抄 solver，否则 UNSPECIFIED。",
                parameters: obj(
                    json!({
                        "solver": {"type": "object"},
                        "connected": {"type": "boolean"}
                    }),
                    &[],
                ),
            },
            ToolDef {
                name: "pack-ship__health",
                description: "装箱拼柜独有：探测 packing-agent 是否接通（URL 或本机仓库）。不编数字。",
                parameters: obj(json!({}), &[]),
            },
            ToolDef {
                name: "material-site__recon",
                description: "现场材料独有：耗用核算表头。无盘点不编盈亏。",
                parameters: obj(
                    json!({
                        "items": {"type": "string"},
                        "notes": {"type": "string"}
                    }),
                    &["items"],
                ),
            },
        ],
        "finance" => vec![
            ToolDef {
                name: "finance__scan_forbidden",
                description: "财务大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "finance-fund__plan",
                description: "资金计划草稿，不编账套分录。",
                parameters: obj(json!({"period": {"type": "string"}, "notes": {"type": "string"}}), &["period"]),
            },
            ToolDef {
                name: "finance-tax__calendar",
                description: "税种与申报节点检查表，不当税务筹划意见。",
                parameters: obj(json!({"jurisdiction": {"type": "string"}}), &[]),
            },
            ToolDef {
                name: "finance-book__check",
                description: "核算独有：账套检查表头。不编分录。",
                parameters: obj(json!({"period": {"type": "string"}}), &["period"]),
            },
        ],
        "docs" => vec![
            ToolDef {
                name: "docs__scan_forbidden",
                description: "资料大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
            name: "supervision__reply",
            description: "监理回复独有：来文复述|拟办|证据目录。暂停/复工只出目录。",
            parameters: obj(
                json!({
                    "notice": {"type": "string"},
                    "reply_points": {"type": "string"}
                }),
                &["notice"],
            ),
        }],
        "hr" => vec![
            ToolDef {
                name: "hr__scan_forbidden",
                description: "人力大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "hr-recruit__brief",
                description: "岗位说明书/面试提纲。不编薪资带宽除非用户给。",
                parameters: obj(json!({"role": {"type": "string"}, "duties": {"type": "string"}}), &["role"]),
            },
            ToolDef {
                name: "hr-labor__check",
                description: "劳动合同/劳务协议检查清单，普法不诉讼。",
                parameters: obj(json!({"contract_type": {"type": "string"}}), &["contract_type"]),
            },
            ToolDef {
                name: "hr-train__plan",
                description: "培训独有：计划骨架。不宣布已培训可上岗。",
                parameters: obj(
                    json!({
                        "audience": {"type": "string"},
                        "topics": {"type": "string"}
                    }),
                    &["audience"],
                ),
            },
        ],
        "admin" => vec![
            ToolDef {
                name: "admin__scan_forbidden",
                description: "行政大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "admin-doc__draft",
                description: "请示/纪要/用印审批口径草稿。",
                parameters: obj(
                    json!({
                        "doc_type": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"}
                    }),
                    &["doc_type", "subject"],
                ),
            },
            ToolDef {
                name: "admin-office__list",
                description: "会务独有：场地/议程清单。不代签发会议决定。",
                parameters: obj(json!({"event": {"type": "string"}}), &["event"]),
            },
        ],
        "it" => vec![
            ToolDef {
                name: "it__scan_forbidden",
                description: "IT 大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "it-ops__runbook",
                description: "账号权限与故障升级路径提纲。",
                parameters: obj(json!({"system": {"type": "string"}}), &["system"]),
            },
            ToolDef {
                name: "it-data__backup",
                description: "备份策略与恢复演练口径。",
                parameters: obj(json!({"systems": {"type": "string"}}), &["systems"]),
            },
            ToolDef {
                name: "it-app__srs",
                description: "应用独有：需求说明书骨架。不编接口地址。",
                parameters: obj(
                    json!({
                        "system": {"type": "string"},
                        "users": {"type": "string"}
                    }),
                    &["system"],
                ),
            },
        ],
        "people" => vec![
            ToolDef {
                name: "people__scan_forbidden",
                description: "现场人员大类共享：扫描成稿里的法定断言句与辖区混用。",
                parameters: obj(json!({"filename": {"type": "string"}}), &["filename"]),
            },
            ToolDef {
                name: "worker-brief__talk",
                description: "3 分钟班前口播稿，给一线工人，禁止断言可以开工。",
                parameters: obj(
                    json!({
                        "work_today": {"type": "string"},
                        "watchouts": {"type": "string"}
                    }),
                    &["work_today"],
                ),
            },
            ToolDef {
                name: "pm-daily__log",
                description: "项目日报：形象进度、人机料、安全质量记事。",
                parameters: obj(
                    json!({
                        "progress": {"type": "string"},
                        "resources": {"type": "string"},
                        "hse": {"type": "string"}
                    }),
                    &["progress"],
                ),
            },
        ],
        _ => vec![],
    }
}

fn live_defs() -> Vec<ToolDef> {
    let mut t = core_tools();
    for c in &seed().categories {
        t.extend(pack_tools(&c.id));
    }
    t
}

fn def_by_name(name: &str) -> Option<ToolDef> {
    live_defs().into_iter().find(|t| t.name == name)
}

/// Shipped visibility: 通用 + 该专家大类共享 + 该专家已实现的独有工具。
pub fn tools_for_expert(expert_id: &str) -> Vec<ToolDef> {
    let allowed = tier_map::assigned_names(expert_id);
    live_defs()
        .into_iter()
        .filter(|t| allowed.iter().any(|n| n == t.name))
        .collect()
}

pub fn tools_for_category(category: &str) -> Vec<ToolDef> {
    tools_for_expert(default_expert(category))
}

pub fn all_tools_filtered(pack: Option<&str>) -> Vec<ToolDef> {
    match pack {
        Some(p) => tools_for_category(p),
        None => live_defs(),
    }
}

pub fn visible_tool_names(expert_id: &str) -> Vec<String> {
    tools_for_expert(expert_id)
        .into_iter()
        .map(|t| t.name.to_string())
        .collect()
}

pub fn pack_help(expert_id: &str, category: &str) -> String {
    let names = visible_tool_names(expert_id);
    let common: Vec<&str> = names
        .iter()
        .filter(|n| tier_map::layer_of(n) == Some(tier_map::ToolLayer::Common))
        .map(|s| s.as_str())
        .collect();
    let cat: Vec<&str> = names
        .iter()
        .filter(|n| tier_map::layer_of(n) == Some(tier_map::ToolLayer::Category))
        .map(|s| s.as_str())
        .collect();
    let excl: Vec<&str> = names
        .iter()
        .filter(|n| tier_map::layer_of(n) == Some(tier_map::ToolLayer::Exclusive))
        .map(|s| s.as_str())
        .collect();
    format!(
        "工具分层（成稿必须调用工具，不要只在聊天里贴表）：\n- 通用：{}\n- {category} 大类共享：{}\n- 本专家独有：{}\n",
        common.join(", "),
        if cat.is_empty() { "（无已实现）".into() } else { cat.join(", ") },
        if excl.is_empty() { "（尚未对齐，先用通用写盘）".into() } else { excl.join(", ") },
    )
}

fn s(args: &Value, key: &str) -> String {
    args.get(key)
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_string()
}

fn opt_f64(args: &Value, key: &str) -> Option<f64> {
    args.get(key).and_then(|v| v.as_f64()).or_else(|| {
        args.get(key)
            .and_then(|v| v.as_str())
            .and_then(|x| x.parse().ok())
    })
}

fn stamp() -> String {
    Local::now().format("%Y-%m-%dT%H-%M-%S").to_string()
}

fn header(title: &str) -> String {
    format!("# {title}\n\n{DISCLAIMER}\n\n- 产出：内部讨论 AI 草稿\n- 时间：{}\n\n", stamp())
}

fn split_lines(raw: &str) -> Vec<String> {
    raw.replace('；', "\n")
        .replace(';', "\n")
        .split('\n')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

pub fn refuse_exclusive(expert_id: &str, name: &str) -> Option<String> {
    if name == "construction__judge_hazard" {
        return Some(
            "拒绝：危大判定是 method-hazard 独有（method-hazard__judge_hazard），当前专家无权调用。".into(),
        );
    }
    if let Some(owner) = tier_map::exclusive_owner(name) {
        if owner != expert_id {
            return Some(format!(
                "拒绝：工具 {name} 是 {owner} 独有，当前专家是 {expert_id}。"
            ));
        }
    }
    if !tier_map::may_call(expert_id, name) && def_by_name(name).is_some() {
        return Some(format!(
            "拒绝：工具 {name} 不在专家 {expert_id} 的三级目录里。"
        ));
    }
    None
}

pub fn execute(ctx: &mut ToolCtx, name: &str, args: &Value) -> String {
    if let Some(msg) = refuse_exclusive(&ctx.expert_id, name) {
        return msg;
    }
    match name {
        "search_kb" => {
            let query = s(args, "query");
            let hits = search_kb(&ctx.paths, &ctx.expert_id, &ctx.category, &query, 6);
            for h in &hits {
                ctx.citations.push(json!({
                    "path": h.path,
                    "layer": h.layer,
                    "layer_label": h.layer_label,
                    "title": h.title,
                    "display": h.title,
                    "snippet": h.snippet
                }));
            }
            serde_json::to_string_pretty(
                &hits
                    .iter()
                    .map(|h| json!({"path": h.path, "layer": h.layer, "title": h.title, "snippet": h.snippet}))
                    .collect::<Vec<_>>(),
            )
            .unwrap_or_else(|_| "[]".into())
        }
        "list_kb" => serde_json::to_string_pretty(&list_kb(&ctx.paths, &ctx.expert_id, &ctx.category))
            .unwrap_or_else(|_| "[]".into()),
        "read_kb" => match read_kb(&ctx.paths, &s(args, "path")) {
            None => "文件不存在或越权".into(),
            Some((rel, text)) => {
                let cut: String = text.chars().take(8000).collect();
                format!("# {rel}\n\n{cut}")
            }
        },
        "write_deliverable" => {
            let filename = s(args, "filename");
            let markdown = s(args, "markdown");
            match ctx.write_md(&filename, &markdown) {
                Ok(m) => m,
                Err(e) => e,
            }
        }
        "web_search" => {
            let query = s(args, "query");
            let out = crate::websearch::run_blocking(|| crate::websearch::search(&query));
            ctx.citations.push(json!({
                "path": format!("web:{query}"),
                "layer": "web",
                "layer_label": "网上检索",
                "title": format!("检索：{query}"),
                "display": format!("检索：{query}"),
                "snippet": out.chars().take(180).collect::<String>(),
            }));
            out
        }
        "web_open" => {
            let url = s(args, "url");
            let out = crate::websearch::run_blocking(|| crate::websearch::open_url(&url));
            ctx.citations.push(json!({
                "path": url,
                "layer": "web",
                "layer_label": "网上检索",
                "title": url,
                "display": url,
                "snippet": out.chars().take(180).collect::<String>(),
            }));
            out
        }
        "list_attachments" => {
            serde_json::to_string_pretty(&crate::attach::list_uploads(&ctx.paths, &ctx.session_id))
                .unwrap_or_else(|_| "[]".into())
        }
        "read_attachment" => {
            let id = s(args, "id");
            let offset = args.get("offset").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
            let limit = args.get("limit").and_then(|v| v.as_u64()).unwrap_or(8000) as usize;
            match crate::attach::read_upload(&ctx.paths, &ctx.session_id, &id, offset, limit) {
                Ok(t) => {
                    ctx.citations.push(json!({
                        "path": format!("upload:{id}"),
                        "layer": "upload",
                        "layer_label": "用户上传",
                        "title": id,
                        "display": format!("上传 {id}"),
                        "snippet": t.chars().take(160).collect::<String>(),
                    }));
                    t
                }
                Err(e) => e,
            }
        }
        "import_local" => match crate::attach::import_local(&ctx.paths, &ctx.session_id, &s(args, "path")) {
            Ok(files) => serde_json::to_string_pretty(&files).unwrap_or_else(|_| "[]".into()),
            Err(e) => format!("导入失败：{e}"),
        },
        "firm__bid_pack" => {
            let v = crate::firm::run_bid_job(&ctx.paths, &ctx.session_id, args);
            if v.get("ok").and_then(|x| x.as_bool()) == Some(true) {
                if let Some(arr) = v.get("files").and_then(|x| x.as_array()) {
                    for f in arr {
                        ctx.deliverables.push(f.clone());
                    }
                }
            }
            v.to_string()
        }
        "bid-parse__extract" => parse_tender(ctx, args),
        "bid__parse_tender" => {
            "拒绝：招标解析是 bid-parse 独有（bid-parse__extract），当前专家无权调用。".into()
        }
        "bid-compliance__gaps" => compliance_gaps(ctx, args),
        "bid-tech__expand" => tech_outline(ctx, args),
        "bid__compliance_gaps" => {
            "拒绝：废标检查是 bid-compliance 独有（bid-compliance__gaps），当前专家无权调用。".into()
        }
        "bid__tech_outline" => {
            "拒绝：技术标是 bid-tech 独有（bid-tech__expand），当前专家无权调用。".into()
        }
        "construction__scheme_draft" => scheme_draft(ctx, args),
        "construction__fill_scheme_docx" => fill_scheme_docx(ctx, args),
        "method-hazard__judge_hazard" => judge_hazard(ctx, args),
        "survey__record" => survey_record(ctx, args),
        "dispatch__daily" => dispatch_daily(ctx, args),
        "warehouse__log" => warehouse_log(ctx, args),
        "pack-ship__list" => pack_ship_list(),
        "pack-ship__plan" => pack_ship_plan(ctx, args),
        "pack-ship__export" => pack_ship_export(args),
        "pack-ship__health" => pack_ship_health(),
        "env__list" => env_list(ctx, args),
        "subcontract__sheet" => subcontract_sheet(ctx, args),
        "structure__calc_outline" => structure_calc(ctx, args),
        "geotech__brief" => geotech_brief(ctx, args),
        "plan-lookahead__week" => plan_lookahead(ctx, args),
        "interim__measure" => interim_measure(ctx, args),
        "plumbing__memo" => plumbing_memo(ctx, args),
        "hvac__memo" => hvac_memo(ctx, args),
        "electrical__memo" => electrical_memo(ctx, args),
        "fire-protect__brief" => fire_protect_brief(ctx, args),
        "steel__memo" => steel_memo(ctx, args),
        "landscape__memo" => landscape_memo(ctx, args),
        "interior__schedule" => interior_schedule(ctx, args),
        "facade__brief" => facade_brief(ctx, args),
        "intel-weak__memo" => intel_weak_memo(ctx, args),
        "civil-defense__brief" => civil_defense_brief(ctx, args),
        "hydraulic__outline" => hydraulic_outline(ctx, args),
        "port__outline" => port_outline(ctx, args),
        "municipal__memo" => municipal_memo(ctx, args),
        "bridge__outline" => bridge_outline(ctx, args),
        "tunnel__outline" => tunnel_outline(ctx, args),
        "traffic__skeleton" => traffic_skeleton(ctx, args),
        "design-coord__minutes" => design_coord_minutes(ctx, args),
        "bim-deliver__lod" => bim_deliver_lod(ctx, args),
        "plan-resource__peak" => plan_resource_peak(ctx, args),
        "proc-vendor__eval" => proc_vendor_eval(ctx, args),
        "material-site__recon" => material_site_recon(ctx, args),
        "lab-record__ledger" => lab_record_ledger(ctx, args),
        "finance-book__check" => finance_book_check(ctx, args),
        "hr-train__plan" => hr_train_plan(ctx, args),
        "admin-office__list" => admin_office_list(ctx, args),
        "it-app__srs" => it_app_srs(ctx, args),
        "construction__judge_hazard" => {
            "拒绝：危大判定是 method-hazard 独有（method-hazard__judge_hazard），当前专家无权调用。".into()
        }
        "construction__scan_forbidden" => scan_forbidden(ctx, args),
        "design__scan_forbidden" => scan_forbidden(ctx, args),
        "bim__scan_forbidden" => scan_forbidden(ctx, args),
        "planning__scan_forbidden" => scan_forbidden(ctx, args),
        "hse__scan_forbidden" => scan_forbidden(ctx, args),
        "commercial__scan_forbidden" => scan_forbidden(ctx, args),
        "bid__scan_forbidden" => scan_forbidden(ctx, args),
        "procurement__scan_forbidden" => scan_forbidden(ctx, args),
        "plant__scan_forbidden" => scan_forbidden(ctx, args),
        "lab__scan_forbidden" => scan_forbidden(ctx, args),
        "finance__scan_forbidden" => scan_forbidden(ctx, args),
        "docs__scan_forbidden" => scan_forbidden(ctx, args),
        "hr__scan_forbidden" => scan_forbidden(ctx, args),
        "admin__scan_forbidden" => scan_forbidden(ctx, args),
        "it__scan_forbidden" => scan_forbidden(ctx, args),
        "people__scan_forbidden" => scan_forbidden(ctx, args),
        "cost__takeoff" => takeoff(ctx, args),
        "commercial__takeoff_table" => {
            "拒绝：工程量拆分是 cost 独有（cost__takeoff），当前专家无权调用。".into()
        }
        "variation__form" => variation(ctx, args),
        "commercial__variation_form" => {
            "拒绝：变更签证是 variation 独有（variation__form），当前专家无权调用。".into()
        }
        "claim__notice" => claim(ctx, args),
        "commercial__claim_notice" => {
            "拒绝：索赔是 claim 独有（claim__notice），当前专家无权调用。".into()
        }
        "lab-mix__report" => mix_outline(ctx, args),
        "lab__mix_outline" => {
            "拒绝：配合比是 lab-mix 独有（lab-mix__report），当前专家无权调用。".into()
        }
        "lab-sample__list" => sample_list(ctx, args),
        "lab__sample_list" => {
            "拒绝：取样清单是 lab-sample 独有（lab-sample__list），当前专家无权调用。".into()
        }
        "safety-brief__talk" => safety_brief(ctx, args),
        "quality__lot" => quality_checklist(ctx, args),
        "emergency__plan" => emergency(ctx, args),
        "hse__safety_brief" => {
            "拒绝：安全交底是 safety-brief 独有（safety-brief__talk），当前专家无权调用。".into()
        }
        "hse__quality_checklist" => {
            "拒绝：质量检查是 quality 独有（quality__lot），当前专家无权调用。".into()
        }
        "hse__emergency_outline" => {
            "拒绝：应急预案是 emergency 独有（emergency__plan），当前专家无权调用。".into()
        }
        "architecture__memo" => discipline_memo(ctx, args),
        "design__discipline_memo" => {
            "拒绝：建筑说明是 architecture 独有（architecture__memo），当前专家无权调用。".into()
        }
        "bim-coord__clash" => clash_minutes(ctx, args),
        "bim-qto__rules" => qto_rules(ctx, args),
        "plan-master__network" => plan_skeleton(ctx, args),
        "bim__clash_minutes" => {
            "拒绝：碰撞纪要是 bim-coord 独有（bim-coord__clash），当前专家无权调用。".into()
        }
        "bim__qto_rules" => {
            "拒绝：算量口径是 bim-qto 独有（bim-qto__rules），当前专家无权调用。".into()
        }
        "planning__plan_skeleton" => {
            "拒绝：总控计划是 plan-master 独有（plan-master__network），当前专家无权调用。".into()
        }
        "proc-compare__table" => compare_table(ctx, args),
        "procurement__compare_table" => {
            "拒绝：比价是 proc-compare 独有（proc-compare__table），当前专家无权调用。".into()
        }
        "proc-plan__schedule" => purchase_plan(ctx, args),
        "procurement__purchase_plan" => {
            "拒绝：采购计划是 proc-plan 独有（proc-plan__schedule），当前专家无权调用。".into()
        }
        "equip__ledger" => equip_ledger(ctx, args),
        "plant__equip_ledger" => {
            "拒绝：设备台账是 equip 独有（equip__ledger），当前专家无权调用。".into()
        }
        "finance-fund__plan" => fund_plan(ctx, args),
        "finance__fund_plan" => {
            "拒绝：资金计划是 finance-fund 独有（finance-fund__plan），当前专家无权调用。".into()
        }
        "finance-tax__calendar" => tax_calendar(ctx, args),
        "finance__tax_calendar" => {
            "拒绝：税务日历是 finance-tax 独有（finance-tax__calendar），当前专家无权调用。".into()
        }
        "supervision__reply" => supervision_reply(ctx, args),
        "docs__supervision_reply" => {
            "拒绝：监理回复是 supervision 独有（supervision__reply），当前专家无权调用。".into()
        }
        "hr-recruit__brief" => job_brief(ctx, args),
        "hr__job_brief" => {
            "拒绝：招聘简报是 hr-recruit 独有（hr-recruit__brief），当前专家无权调用。".into()
        }
        "hr-labor__check" => labor_checklist(ctx, args),
        "admin-doc__draft" => admin_doc(ctx, args),
        "it-ops__runbook" => ops_outline(ctx, args),
        "hr__labor_checklist" => {
            "拒绝：劳动合同检查是 hr-labor 独有（hr-labor__check），当前专家无权调用。".into()
        }
        "admin__doc_draft" => {
            "拒绝：公文草稿是 admin-doc 独有（admin-doc__draft），当前专家无权调用。".into()
        }
        "it__ops_outline" => {
            "拒绝：运维手册是 it-ops 独有（it-ops__runbook），当前专家无权调用。".into()
        }
        "it-data__backup" => backup_policy(ctx, args),
        "it__backup_policy" => {
            "拒绝：备份策略是 it-data 独有（it-data__backup），当前专家无权调用。".into()
        }
        "worker-brief__talk" => worker_brief(ctx, args),
        "pm-daily__log" => pm_daily(ctx, args),
        "people__worker_brief" => {
            "拒绝：班前白话是 worker-brief 独有（worker-brief__talk），当前专家无权调用。".into()
        }
        "people__pm_daily" => {
            "拒绝：项目日报是 pm-daily 独有（pm-daily__log），当前专家无权调用。".into()
        }
        other => format!("未知工具 {other}"),
    }
}

fn gather_tender_source(ctx: &ToolCtx, args: &Value) -> String {
    let mut chunks = Vec::new();
    for key in ["tender_text", "text", "excerpt", "source", "body"] {
        let v = s(args, key);
        if !v.is_empty() {
            chunks.push(v);
        }
    }
    for f in crate::attach::list_uploads(&ctx.paths, &ctx.session_id) {
        let Some(id) = f.get("id").and_then(|v| v.as_str()) else {
            continue;
        };
        if let Ok(body) = crate::attach::read_upload(&ctx.paths, &ctx.session_id, id, 0, 20_000) {
            chunks.push(body);
        }
    }
    chunks.join("\n")
}

fn parse_tender(ctx: &mut ToolCtx, args: &Value) -> String {
    let text = gather_tender_source(ctx, args);
    if text.trim().is_empty() {
        return "拒绝写盘：没有招标正文。请粘贴 ITT 或上传 pdf/docx/xlsx/txt 后再抽。".into();
    }
    let project = nonempty(&s(args, "project_name"), "未命名招标");
    let (jur, banner) = zone_banner(args);
    let facts = crate::extract::facts_from_text(&text);
    let portal = if jur == "SG" || jur == "DUAL" {
        "官方门户标题：Price Quality Method (PQM) Framework（BCA，页述 Last updated 26 January 2026；适用 CW01/CW02 公共施工、估算造价不含 contingency ≥ S$3 million）。本项目权重只抄 ITT 原文，不把框架区间当作本标分数。GeBIZ 只是发布渠道。CSOC / Apply WSH in Construction Sites 只当招标点名课程，本表不发证。未抽出的 SS/CP/BCA 条款写 UNSPECIFIED，禁止补编分数。"
    } else {
        "辖区非 SG：评标办法以招标文件原文为准，禁止补编分数或条款号。"
    };
    let md = format!(
        "{}{banner}\n## 工程\n{project}\n\n## 评标权重表\n{}\n\n## 评分点摘录\n{}\n\n## Workhead / 资质对照\n{}\n\n## Two Envelope\n{}\n\n## 资质/证书\n{}\n\n## 工期\n{}\n\n## 必须编制的专项（触发清单）\n{}\n\n{portal}\n未抽出的栏目写「未在原文检出」。[A001] 原文未给的数字一律待填。\n",
        header(&format!("{project} · 招标解析表")),
        score_weight_table(&facts),
        bullets_or(&facts.scores, "未在原文检出评分点"),
        workhead_table(&facts),
        envelope_block(&facts),
        bullets_or(&facts.quals, "未在原文检出资质要求"),
        bullets_or(&facts.duration, "未在原文检出工期"),
        bullets_or(&facts.specials, "未在原文检出专项要求"),
    );
    match ctx.write_md("招标解析表.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn classify_gap_item(raw: &str) -> (String, String) {
    let t = raw.trim();
    if let Some((cat, rest)) = t.split_once('|') {
        let cat = cat.trim();
        if matches!(cat, "评分" | "workhead" | "信封" | "专项" | "资质" | "工期") {
            return (cat.to_string(), rest.trim().to_string());
        }
    }
    let low = t.to_ascii_lowercase();
    let cat = if low.contains("cw0") || low.contains("workhead") {
        "workhead"
    } else if low.contains("envelope") || t.contains("双信封") || t.contains("分投") {
        "信封"
    } else if t.contains("专项") || low.contains("method statement") {
        "专项"
    } else if t.contains("分") || low.contains("score") || low.contains("quality") || low.contains("price") {
        "评分"
    } else {
        "资质"
    };
    (cat.to_string(), t.to_string())
}

fn compliance_gaps(ctx: &mut ToolCtx, args: &Value) -> String {
    let required = split_lines(&s(args, "required_items"));
    let notes = s(args, "response_notes");
    let mut rows = String::from("| 类别 | 要求 | 拟响应摘录 | 缺口 |\n| --- | --- | --- | --- |\n");
    for item in &required {
        let (cat, req) = classify_gap_item(item);
        let hit = notes.contains(&req) || (!notes.is_empty() && req.chars().take(4).all(|c| notes.contains(c)));
        let gap = if notes.is_empty() {
            "未提供响应材料"
        } else if hit {
            "见响应摘录，仍须人工核对"
        } else {
            "原文未见对应响应，易废标"
        };
        rows.push_str(&format!("| {cat} | {req} | {} | {gap} |\n", clip(&notes, 40)));
    }
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n{rows}\n本表不是投标承诺。{}\n",
        header("废标/响应缺口清单"),
        sg_only(&jur, "SG：GeBIZ / PQM 只写门户，不编分数。")
    );
    match ctx.write_md("响应缺口清单.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn tech_outline(ctx: &mut ToolCtx, args: &Value) -> String {
    let points = split_lines(&s(args, "scoring_points"));
    let project = nonempty(&s(args, "project_name"), "未命名项目");
    let (jur, banner) = zone_banner(args);
    let mut body = header(&format!("{project} · 技术标目录草稿"));
    body.push_str(&format!("{banner}\n按评分点扩写，分数未核验则标未核实。条款 [UNSPECIFIED]。\n\n"));
    for (i, p) in points.iter().enumerate() {
        body.push_str(&format!("## {}. {p}\n\n- 要点：待按招标原文扩写\n- 附图/附表：待填\n- 条款：[UNSPECIFIED]\n\n", i + 1));
    }
    if points.is_empty() {
        body.push_str("## 1 总则\n\n评分点未提供，目录待填。\n");
    }
    body.push_str(&sg_only(
        &jur,
        "\nSG：GeBIZ / PQM 只写门户，分数以招标原文为准，禁止补编。\n",
    ));
    match ctx.write_md("技术标目录草稿.md", &body) {
        Ok(m) => m,
        Err(e) => e,
    }
}

pub fn normalize_jurisdiction(raw: &str) -> String {
    let t = raw.trim();
    if t.is_empty() {
        return "SG".into();
    }
    let u = t.to_ascii_uppercase();
    match u.as_str() {
        "SG" | "SINGAPORE" | "SGP" => "SG".into(),
        "新加坡" => "SG".into(),
        "CN" | "CHINA" => "CN".into(),
        "EU" => "EU".into(),
        "DUAL" => "DUAL".into(),
        _ if t.contains("新加坡") || t.to_ascii_lowercase().contains("singapore") => "SG".into(),
        _ => u,
    }
}

fn gather_scheme_facts(ctx: &ToolCtx, args: &Value) -> String {
    let mut parts = Vec::new();
    for key in [
        "known_facts",
        "work_scope",
        "site_name",
        "project_name",
        "brief",
        "task",
        "description",
    ] {
        let v = s(args, key);
        if !v.is_empty() {
            parts.push(format!("{key}: {v}"));
        }
    }
    if let Some(h) = opt_f64(args, "height_m") {
        parts.push(format!("height_m: {h}"));
    }
    if let Some(d) = opt_f64(args, "excavation_depth_m") {
        parts.push(format!("excavation_depth_m: {d}"));
    }
    for f in crate::attach::list_uploads(&ctx.paths, &ctx.session_id) {
        let Some(id) = f.get("id").and_then(|v| v.as_str()) else {
            continue;
        };
        if let Ok(body) = crate::attach::read_upload(&ctx.paths, &ctx.session_id, id, 0, 8_000) {
            parts.push(body);
        }
    }
    parts.join("\n")
}

fn scheme_draft(ctx: &mut ToolCtx, args: &Value) -> String {
    let project = nonempty(&s(args, "project_name"), "未命名工程");
    let scope = nonempty(&s(args, "work_scope"), "待填");
    let (jur, banner) = zone_banner(args);
    let site = nonempty(&s(args, "site_name"), "Singapore site");
    let gathered = gather_scheme_facts(ctx, args);
    let facts = if gathered.trim().is_empty() {
        "（用户未提供，整节待填）".to_string()
    } else {
        gathered
    };
    let unknowns = nonempty(&s(args, "unknowns"), "临边高度、护栏规格、工作平台、岩土/荷载未提供");
    let user_blob = format!("{project} {scope} {facts} {unknowns} {}", s(args, "jurisdiction"));
    let basis = if jur == "SG" || jur == "DUAL" {
        "### 已核实\n\n（无 — 未抽出 SS / CP / BCA / WSH / SCDF / PUB 原文）\n\n### 未核实 / UNSPECIFIED\n\n- Workplace Safety and Health Act / WSH (Construction) Regulations 2007：条款 UNSPECIFIED\n- BCA Building Control Act / Approved Document：条款 UNSPECIFIED\n- SCDF Fire Code 2023（Code of Practice for Fire Precautions in Buildings 2023）：只列章名\n- PUB Codes of Practice（Surface Water Drainage / Sewerage and Sanitary Works）：条款 UNSPECIFIED\n- SS / CP（工作于高处、临边防护相关）：编号与条款 UNSPECIFIED\n- [A001] 未提供的尺寸与参数一律待填\n\n禁止把中国大陆规范条文当作新加坡依据。DUAL 时必须同时点名 SG 与另一辖区，不得静默混用。"
    } else {
        "### 已核实\n\n（无）\n\n### 未核实 / UNSPECIFIED\n\n用户未抽出规范原文，条款号不得编造。禁止静默混入其他辖区条文。"
    };
    let safety = if jur == "SG" || jur == "DUAL" {
        "工作于高处 / 临边：按现场 PTW 与 WSH 管理，由持证人员判定。本处不写开工许可或报审结论。危大/论证类判定请改召唤 method-hazard。"
    } else {
        "危大判定请改召唤 method-hazard。本处不写开工或报审类断言。"
    };
    let md = format!(
        "# {project} 专项施工方案讨论提纲（AI 草稿）\n\n{DISCLAIMER}\n\n{banner}- 工地：{site}\n- 工作范围：{scope}\n- [A001] {unknowns}\n\n## 1 封面与文件控制\n\nPE / QP / 签认栏留空。本文件不是法定 method statement，也不是 WSH 签发件。\n\n## 2 草稿与责任声明\n\n{DISCLAIMER}\n\n## 3 工程概况\n\n{facts}\n\n不得默写栏杆高度、水平荷载、踢脚板高度。无来源整节待填。\n\n## 4 编制依据\n\n{basis}\n\n## 5 施工部署与工艺\n\n待按 {site} 现场条件填写。无图纸不编步骤参数。\n\n## 6 质量\n\n检查表头 + 待填。不给合格结论。\n\n## 7 安全与应急\n\n{safety}\n\n## 8 环保与文明施工\n\n扬尘、弃土、夜间施工口径待填。\n\n## 9 资源计划\n\n| 资源 | 规格 | 数量 | 备注 |\n| --- | --- | --- | --- |\n| TBD | TBD | TBD | 无清单不编用量 |\n\n## 10 验收与资料\n\n资料目录待填。不给验收通过结论。\n\n## 11 附录\n\n图号清单：未提供则禁止写「见图」。\n"
    );
    if invented_sg_or_cn_codes(&md, &user_blob) {
        return "拒绝写盘：成稿出现未在用户输入中的 SS/CP/GB/JGJ 条款号，改为 UNSPECIFIED。".into();
    }
    match ctx.write_md("专项方案-AI草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn invented_sg_or_cn_codes(text: &str, user_blob: &str) -> bool {
    let re = regex::Regex::new(r"\b(?:SS|CP|GB|JGJ|JG/T)\s*[0-9]{2,}").expect("code re");
    for m in re.find_iter(text) {
        let token = m.as_str();
        if !user_blob.contains(token) {
            return true;
        }
    }
    false
}

fn fill_scheme_docx(ctx: &mut ToolCtx, args: &Value) -> String {
    if let Err(e) = ctx.gate() {
        return e;
    }
    let project = nonempty(&s(args, "project_name"), "未命名工程");
    let (jur, _banner) = zone_banner(args);
    let draft_name = nonempty(&s(args, "draft_filename"), "专项方案-AI草稿.md");
    let draft = ctx.out_dir.join(&draft_name);
    if !draft.is_file() {
        return format!("找不到 {draft_name}，请先调用 construction__scheme_draft");
    }
    let assumptions = ctx.out_dir.join("assumptions.md");
    if !assumptions.is_file() {
        let _ = fs::write(
            &assumptions,
            format!("# 假设\n\n- [A001] 用户未提供的尺寸、荷载、岩土参数一律待填。\n- 工程：{project}\n"),
        );
    }
    let citations = ctx.out_dir.join("citations.md");
    if !citations.is_file() {
        let _ = fs::write(
            &citations,
            "# 已核实\n\n（无）\n\n# 未核实 / UNSPECIFIED\n\n未抽出规范原文。\n",
        );
    }
    if !ctx.paths.fill_scheme_py.is_file() {
        return format!("缺少填模脚本 {}", ctx.paths.fill_scheme_py.display());
    }
    let out_docx = ctx.out_dir.join("专项施工方案-AI草稿.docx");
    let short: String = project.chars().take(12).collect();
    let status = run_python(&[
        ctx.paths.fill_scheme_py.to_string_lossy().as_ref(),
        "--template",
        ctx.paths.template_docx.to_string_lossy().as_ref(),
        "--draft",
        draft.to_string_lossy().as_ref(),
        "--assumptions",
        assumptions.to_string_lossy().as_ref(),
        "--citations",
        citations.to_string_lossy().as_ref(),
        "--jurisdiction",
        &jur,
        "--stamp",
        &stamp(),
        "--project-name",
        &project,
        "--short-name",
        &short,
        "--out",
        out_docx.to_string_lossy().as_ref(),
    ]);
    match status {
        Ok(out) => {
            if out_docx.is_file() {
                ctx.deliverables.push(json!({
                    "expert": ctx.expert_id,
                    "name": "专项施工方案-AI草稿.docx",
                    "path": out_docx.to_string_lossy(),
                    "docx_pending": false,
                }));
                format!("fill_scheme_docx: {out}")
            } else {
                ctx.deliverables.push(json!({
                    "expert": ctx.expert_id,
                    "name": "专项方案-AI草稿.md",
                    "path": draft.to_string_lossy(),
                    "docx_pending": true,
                }));
                format!("fill_scheme_docx: docx_pending; {out}")
            }
        }
        Err(e) => {
            ctx.deliverables.push(json!({
                "expert": ctx.expert_id,
                "name": "专项方案-AI草稿.md",
                "path": draft.to_string_lossy(),
                "docx_pending": true,
            }));
            format!("fill_scheme_docx: docx_pending; {e}")
        }
    }
}

fn judge_hazard(ctx: &mut ToolCtx, args: &Value) -> String {
    let work = nonempty(&s(args, "work_type"), "未说明作业");
    let desc = s(args, "description");
    let (jur, banner) = zone_banner(args);
    let h = opt_f64(args, "height_m");
    let d = opt_f64(args, "excavation_depth_m");
    let blob = format!("{work} {desc}");
    let sg = jur == "SG" || jur == "DUAL";
    let cn_triggers = ["基坑", "脚手架", "模板", "支撑", "起重", "有限空间", "拆除", "爆破", "暗挖", "顶管"];
    let sg_triggers = [
        "excavation",
        "demolition",
        "piling",
        "tunnel",
        "crane",
        "scaffold",
        "拆除",
        "开挖",
        "打桩",
        "起重",
        "脚手架",
        "临边",
        "work at height",
        "working at height",
    ];
    let hit_word = if sg {
        sg_triggers
            .iter()
            .any(|w| blob.to_ascii_lowercase().contains(&w.to_ascii_lowercase()))
    } else {
        cn_triggers.iter().any(|w| blob.contains(*w))
    };
    let (verdict, reason) = if sg {
        if hit_word || h.map(|x| x >= 2.0).unwrap_or(false) || d.map(|x| x >= 1.5).unwrap_or(false) {
            (
                "可能落入新加坡高风险作业口径，须由持证人员按 WSH 风险评估与 PTW 正式判定",
                "命中开挖/拆除/起重/临边等公开高风险类型。不套用中国危大工程规定。本工具不签发 PTW。CSOC / Apply WSH in Construction Sites 不是 PTW。",
            )
        } else if h.is_none() && d.is_none() && !hit_word {
            (
                "信息不足，不能判定",
                "[A001] 未提供作业高度、开挖深度或结构形式。禁止用本结论代替 PTW 或当作可以作业。",
            )
        } else {
            (
                "当前输入未命中本工具内置 SG 触发条件，仍须现场 RA",
                "不得据此写已经可以作业。中国危大口径不适用于本判定。",
            )
        }
    } else if h.map(|x| x >= 2.0).unwrap_or(false) || d.map(|x| x >= 3.0).unwrap_or(false) || hit_word {
        (
            "可能属于危大工程范围，须由持证人员按项目适用的危大管理规定正式判定",
            "命中高度/深度阈值或常见危大触发词。本工具不签发论证，不替代专家论证会。",
        )
    } else if h.is_none() && d.is_none() && !hit_word {
        (
            "信息不足，不能判定",
            "[A001] 未提供作业高度、开挖深度或结构形式。禁止用本结论报审或当作已经可以作业。",
        )
    } else {
        (
            "当前输入未命中本工具内置触发条件，仍须现场核对",
            "未检出常见危大触发。不得据此写非危大即可作业。",
        )
    };
    let md = format!(
        "{}{banner}\n## 作业\n- 类型：{work}\n- 高度 m：{}\n- 开挖深度 m：{}\n- 描述：{}\n\n## 判定（非正式）\n**{verdict}**\n\n{reason}\n\n禁止写开工/报审/论证类断言句（见公司硬规则）。\n",
        header("危大判定书（AI 草稿）"),
        h.map(|x| x.to_string()).unwrap_or_else(|| "未提供".into()),
        d.map(|x| x.to_string()).unwrap_or_else(|| "未提供".into()),
        nonempty(&desc, "未提供"),
    );
    match ctx.write_md("危大判定书.md", &md) {
        Ok(m) => format!("{m}\n判定：{verdict}"),
        Err(e) => e,
    }
}

const ASSERTIVE: &[&str] = &[
    "可交差",
    "可报审",
    "报审通过",
    "可提交专家论证",
    "请专家论证",
    "请监理审核后开工",
    "请监理审核",
    "可以开工",
    "已具备报审条件",
];

fn forbidden_hits(text: &str) -> Vec<&'static str> {
    let mut hits: Vec<&str> = ASSERTIVE.iter().copied().filter(|p| text.contains(p)).collect();
    let sg_draft = text.contains("辖区：SG") || text.contains("- 辖区：SG");
    if sg_draft {
        for p in ["37 号令", "第 37 号", "建办质", "JGJ", "GB 50", "住建部令", "增值税"] {
            if text.contains(p) && !hits.contains(&p) {
                hits.push(p);
            }
        }
    }
    hits
}

fn scan_forbidden(ctx: &mut ToolCtx, args: &Value) -> String {
    let filename = s(args, "filename");
    let path = ctx.out_dir.join(Path::new(&filename).file_name().unwrap_or_default());
    let Ok(text) = fs::read_to_string(&path) else {
        return format!("读不到 {}", path.display());
    };
    let hits = forbidden_hits(&text);
    if hits.is_empty() {
        "扫描通过：未检出法定断言句。".into()
    } else {
        format!("扫描未通过，检出：{}", hits.join("、"))
    }
}

fn gather_takeoff_lines(ctx: &ToolCtx, args: &Value) -> Vec<String> {
    let mut lines = split_lines(&s(args, "items"));
    for f in crate::attach::list_uploads(&ctx.paths, &ctx.session_id) {
        let Some(id) = f.get("id").and_then(|v| v.as_str()) else {
            continue;
        };
        if let Ok(body) = crate::attach::read_upload(&ctx.paths, &ctx.session_id, id, 0, 20_000) {
            for raw in body.lines() {
                let t = raw.trim();
                if t.is_empty() || t.starts_with('【') || t.starts_with("offset=") {
                    continue;
                }
                if t.contains("综合单价") && (t.contains("分项") || t.contains("单位")) {
                    continue;
                }
                lines.push(t.to_string());
            }
        }
    }
    if lines.is_empty() {
        lines.push("未提供分项 [A001]".into());
    }
    lines
}

fn takeoff(ctx: &mut ToolCtx, args: &Value) -> String {
    let project = nonempty(&s(args, "project_name"), "未命名");
    let (jur, banner) = zone_banner(args);
    let items = gather_takeoff_lines(ctx, args);
    let mut table = format!(
        "{}{banner}\n## {project}\n\n| 分项 | 单位 | 数量 | 综合单价 | 合价 | 备注 |\n| --- | --- | --- | --- | --- | --- |\n",
        header("工程量拆分表")
    );
    for it in items {
        table.push_str(&format!(
            "| {it} | TBD | TBD | UNSPECIFIED | UNSPECIFIED | 无清单不编单价 |\n"
        ));
    }
    table.push_str("\n金额一律 UNSPECIFIED。[A001] 无清单/报价则合价待填。禁止编造综合单价，禁止补编清单条款号。");
    table.push_str(&sg_only(&jur, "SG：PSSCOC 计量条款只写族名。"));
    table.push('\n');
    match ctx.write_md("工程量拆分表.md", &table) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn classify_variation_kind(blob: &str) -> String {
    let low = blob.to_ascii_lowercase();
    let mut hits: Vec<&str> = Vec::new();
    if blob.contains("设计变更") || low.contains("design change") {
        hits.push("设计变更");
    }
    if blob.contains("工程签证") || blob.contains("签证") || low.contains("variation") {
        hits.push("工程签证");
    }
    if blob.contains("洽商") {
        hits.push("工程洽商");
    }
    if blob.contains("联系单") {
        hits.push("工程联系单");
    }
    if blob.contains("工程量确认") || low.contains("qty confirm") {
        hits.push("工程量确认单");
    }
    hits.dedup();
    if hits.len() > 1 {
        "混写，须拆开。本表不混写，待用户指定一类。".into()
    } else if hits.len() == 1 {
        hits[0].to_string()
    } else {
        "信息不足，待用户指定一类（设计变更 / 工程签证 / 工程洽商 / 工程联系单 / 工程量确认单）。".into()
    }
}

fn copy_variation_no(blob: &str) -> String {
    let re = regex::Regex::new(r"(?i)\b(?:VO|SI|DC|VAR)[-_./]?\d+[A-Za-z]?\b").expect("vo re");
    let mut rows = Vec::new();
    for line in blob.lines() {
        let t = line.trim();
        if t.is_empty() {
            continue;
        }
        if t.contains("变更编号") || re.is_match(t) {
            rows.push(t.chars().take(160).collect::<String>());
        }
    }
    if rows.is_empty() {
        "变更编号待填。禁止引用未提供的图号。条款号 UNSPECIFIED。".into()
    } else {
        rows.iter().map(|r| format!("- {r}")).collect::<Vec<_>>().join("\n")
    }
}

fn variation(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let facts = nonempty(&s(args, "event_facts"), "");
    let facts = if facts.is_empty() {
        nonempty(&s(args, "event"), "整节待填。[A001]")
    } else {
        facts
    };
    let basis = nonempty(&s(args, "basis"), "");
    let qty = nonempty(&s(args, "qty_note"), "待计量");
    let blob = format!("{facts}\n{basis}\n{qty}");
    let kind = classify_variation_kind(&blob);
    let mut no_blob = blob.clone();
    if basis != "待填 / UNSPECIFIED" && !basis.is_empty() {
        no_blob.push('\n');
        no_blob.push_str(&basis);
    }
    let var_no = copy_variation_no(&no_blob);
    let md = format!(
        "{}{banner}\n## 1 封面与草稿声明\n不构成已签认签证，不替代设计变更通知单。金额 TBD。\n\n## 2 文件类型判定\n本表文种：**{kind}**。只选一类。\n\n## 3 事实栏\n{facts}\n\n时间/部位/事由/谁提出：用户未给的格子待填。[A001]\n\n## 4 依据栏\n{var_no}\n\n合同条款只写名称，不编条款号。无用户变更编号则依据待填。\n\n## 5 工程量栏\n{qty}\n\n计算式或现场实测待填。与原清单对应编码无则新建项待定。[A001]\n\n## 6 价款调整方法\n只写路径，不填数：有适用单价则用该单价；只有类似单价则参照并说明差异；都没有则协商，人材机口径单价 TBD。\n\n## 7 签认栏\n| 角色 | 姓名 | 日期 |\n| --- | --- | --- |\n| 监理对事实 |  |  |\n| 造价对价款 |  |  |\n\n空栏，不代签。不把现场确认写成已定价。\n\n## 8 与索赔、验工的接口\n指令内调价走本节。指令外损失走索赔调概（claim）。当期计量走验工计价（interim）。\n\n## 9 附件目录\n照片/实测草图/变更单扫描/原清单摘录：有则列名，无则写用户未提供。\n\n## 10 自检\n无金额编造。无事后补签装成当时签。不编无来源限额。\n\n{}\n",
        header("变更签证单草稿"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：PSSCOC 2020 / PSSCOC-lite 2025 / SIA / REDAS 只写合同族名，条款 UNSPECIFIED。"),
            cn_only(&jur, "CN：GF-2017-0201 / GB/T 50500-2024 只写全名；财建〔2004〕369 号程序是否适用看用户合同，不编确认天数。"),
        ),
    );
    match ctx.write_md("签证单草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn copy_claim_evidence(blob: &str) -> String {
    const KEYS: &[&str] = &[
        "函",
        "通知",
        "停工",
        "天气",
        "影像",
        "照片",
        "试验",
        "会议纪要",
        "回证",
        "letter",
        "notice",
        "photo",
        "record",
    ];
    let mut rows = Vec::new();
    for raw in blob.replace('；', "\n").replace(';', "\n").lines() {
        let t = raw.trim();
        if t.is_empty() || t == "待列" || t == "待补" {
            continue;
        }
        let low = t.to_ascii_lowercase();
        if KEYS.iter().any(|k| t.contains(k) || low.contains(&k.to_ascii_lowercase())) {
            rows.push(format!("- {}（只抄用户已给）", t.chars().take(160).collect::<String>()));
        }
    }
    if rows.is_empty() {
        "| 证据 | 状态 |\n| --- | --- |\n| 往来函 / 监理通知 / 停工令 | 待补 |\n| 天气或停水停电记录 | 待补 |\n| 人员机械进出场 / 影像 / 试验报告 | 待补 |\n| 采购合同 / 会议纪要 / 送达回证 | 待补 |".into()
    } else {
        rows.join("\n")
    }
}

fn claim(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let event = nonempty(&s(args, "event"), "整节待填。[A001]");
    let evidence_raw = nonempty(&s(args, "evidence"), "");
    let clock = nonempty(&s(args, "deadline_note"), "用户合同索赔条款原文待贴。时限未提供，待按合同核对。");
    let blob = format!("{event}\n{evidence_raw}\n{clock}");
    let evidence = copy_claim_evidence(&blob);
    let md = format!(
        "{}{banner}\n## 1 封面与草稿声明\n不是已送达的索赔报告，不构成调概批复。工期天数 TBD。金额 TBD。条款原文待贴。\n\n## 2 事件识别\n{event}\n\n费用索赔与工期索赔分列。变更指令内调价优先走变更签证（variation），不重复当索赔。\n\n## 3 合同时钟\n{clock}\n\n不编条款号。只提示逾期风险，不断言已失权。\n\n## 4 意向通知必备\n| 栏 | 内容 |\n| --- | --- |\n| 事件事由 | 只抄用户原文 |\n| 发生时间 | 待填 |\n| 合同依据名称 | 待贴原文 |\n| 可能费用和／或工期 | TBD |\n| 已采取减损 | 待填 |\n| 证据目录 | 见第 5 节 |\n\n不填索赔总价。\n\n## 5 证据清单\n{evidence}\n\n## 6 因果与责任栏\n事件 → 影响工作面 → 关键线路是否被占（无网络图则工期影响待填）→ 己方有无扩大损失。[A001]\n\n## 7 费用组成口径\n| 组成 | 单价 |\n| --- | --- |\n| 人工停置 | TBD |\n| 机械停滞 | TBD |\n| 材料仓储或贬值 | TBD |\n| 赶工 | TBD |\n| 利润（是否计取看合同） | TBD |\n| 总部管理费 | TBD |\n\n## 8 调概专节\n政府投资调概只出事项对照表。预备费能覆盖的不调概。本岗不下报批结论。\n\n## 9 与签证、验工接口\n能签认的事实先固定在签证。索赔成立后的金额进验工计价，无业主确认不编入当期付款。\n\n## 10 自检\n无编造条款号。无编造索赔额。无胜诉或必然支持。\n\n{}\n",
        header("索赔意向草稿"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：Building and Construction Industry Security of Payment Act 只写全名，时限 UNSPECIFIED。PSSCOC-lite 2025 / Clause 23 Procedure for Claims 只写条名。"),
            cn_only(&jur, "CN：GF-2017-0201 索赔意向/报告天数以用户合同为准。发改投资〔2015〕482 号只写全名。GB 50500 只出现在 CN 栏。"),
        ),
    );
    match ctx.write_md("索赔意向草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn mix_has_trial(args: &Value) -> bool {
    if let Some(b) = args.get("has_trial_data").and_then(|v| v.as_bool()) {
        return b;
    }
    let blob = format!("{} {} {}", s(args, "material"), s(args, "notes"), s(args, "text"));
    if blob.contains("无试验数据") {
        return false;
    }
    ["已有试验数据", "试配记录", "试拌记录", "含水率已测", "试验室配合比已批"]
        .iter()
        .any(|k| blob.contains(k))
}

fn mix_outline(ctx: &mut ToolCtx, args: &Value) -> String {
    let has = mix_has_trial(args);
    let (jur, banner) = zone_banner(args);
    let material = nonempty(&s(args, "material"), "[A001] 待填");
    let notes = nonempty(&s(args, "notes"), "无");
    let kind = if material.contains('M') && !material.to_ascii_uppercase().contains('C') {
        "砂浆"
    } else if material.contains("砂浆") {
        "砂浆"
    } else {
        "混凝土"
    };
    let layer4 = if has {
        "用户声明已有试验数据：可列换算栏，施工配比数字仍须试验室签认。本稿不编 kg/m³。"
    } else {
        "无试验数据：不给施工配合比，整节待填。含水率未测不得换算湿料。"
    };
    let four = format!(
        "| 层次 | 本稿 |\n| --- | --- |\n| 初步（理论）配合比 | 缺原材料密度、含水、需水量则停。用量待填。 |\n| 基准配合比 | 无试拌记录不锁基准。 |\n| 试验室配合比 | 强度与耐久性复核通过后才能作为换算起点。 |\n| 施工配合比 | {layer4} |"
    );
    let basis = if jur == "SG" {
        "公开名称只写族名。条款 unspecified_clause。用户未提供文本则不得写入已核实块，不得摘条款。".to_string()
    } else {
        "公开名称，年份以项目现行有效版为准，状态 unverified / unspecified_clause。《普通混凝土配合比设计规程》JGJ 55；《砌筑砂浆配合比设计规程》JGJ/T 98；《混凝土质量控制标准》GB 50164；《混凝土结构工程施工质量验收规范》GB 50204；《预拌混凝土》GB/T 14902。用户未提供文本则不得写入已核实块，不得摘条款。".to_string()
    };
    let md = format!(
        "{}{banner}\n本提纲不是法定配合比报告，不是搅拌站开盘依据，不构成浇筑许可。种类：{kind}。\n\n## 1 封面与文件控制\n工程名称待填。部位待填。强度等级/砂浆等级：{material}。坍落度或稠度要求待填。全部只引用户或项目包。空签认栏。[A001]\n\n## 2 草稿声明\n不是法定配合比报告，不是搅拌站开盘依据。\n\n## 3 选用口径\n{four}\n\n只写层次，不写用量。砂浆与混凝土分开写，预拌与现场拌合分开写。\n\n## 4 原材料一致性\n水泥、掺合料、砂、石、外加剂、拌合水须与试配时同一品种、规格、产地口径。进场复试未出或异常，不得换算施工配比，也不得自行改砂率、水胶比、外加剂掺量。\n\n## 5 调整权限\n试验员可记录含水率和开盘观察，不得口头改配比。超出批准范围的调整要试验数据 + 试验室主任/技术负责人 + 监理/建设知情。本提纲不代批。\n\n## 6 编制依据\n{basis}\n\n## 7 与见证取样、台账的接口\n| 编号 | 本稿 |\n| --- | --- |\n| 原材料复试报告编号 | 待填 |\n| 试配记录编号 | 待填 |\n| 开盘鉴定记录编号 | 待填 |\n\n有则抄用户，无则待填。编号规则见 lab-record，本岗不编新号。\n\n## 8 资料目录\n试配申请、原材料报告、试拌记录、强度/耐久性试件、批准的试验室配合比、含水率测定、施工配合比通知单。开盘条件栏待核，本稿不下开盘结论。\n\n## 9 禁令\n不编水胶比、砂率、每立方米用量、水泥强度、外加剂掺量。不把搅拌站经验配比或网上例题当成工程配比。不因商务催省水泥而改单。\n\n备注：{notes}\n\n{}\n",
        header("配合比报告提纲"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：SAC laboratory accreditation / CT 06 Ready-Mixed Concrete Producers 只写标题。SS EN 206 / SS 544 只写族名。不得把已过时的 SS 289 / CP 65 当现行配比依据。"),
            cn_only(&jur, "CN：普通混凝土配合比设计规程只写全名，不给施工配比。"),
        ),
    );
    match ctx.write_md("配比报告提纲.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn sample_list(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let mut mats = split_lines(&s(args, "materials"));
    if mats.is_empty() {
        mats = vec![
            "承重结构混凝土试块".into(),
            "承重墙体砌筑砂浆试块".into(),
            "承重结构钢筋及连接接头试件".into(),
            "承重墙的砖和混凝土小型砌块".into(),
            "拌制混凝土和砌筑砂浆的水泥".into(),
            "承重结构混凝土用掺加剂".into(),
            "地下、屋面、厕浴间防水材料".into(),
            "国家规定的其他项目（地方加长项待核）".into(),
        ];
    }
    let mut table = String::from(
        "| 类别 | 部位 | 见证人 | 组数 | 升级路径 |\n| --- | --- | --- | --- | --- |\n",
    );
    for m in &mats {
        table.push_str(&format!(
            "| {m} | 待填 | （空） | [A001] | 不合格 24 小时上报；停止相关使用；隔离待处置 |\n"
        ));
    }
    let md = format!(
        "{}{banner}\n本清单只排计划与缺口，不判定材料合格，不编组数。不是工程质量验收资料。\n\n## 1 封面\n工程名称、施工段、计划周期、检测机构名称待填（须用户给出且为建设委托）。空签认栏。[A001]\n\n## 2 角色\n取样员属施工单位；见证人属建设单位或监理。取样员与见证人不得写成同一人同一单位。建设委托的检测，施工人员须在见证下现场取样。\n\n## 3 必须纳入见证取样的类别\n{table}\n全国公开底线只列名称。地方加长项待核，不编造地方条款。\n\n## 4 比例口径\n涉及结构安全的试块、试件和材料，见证取样和送检比例不得低于有关技术标准规定应取样数量的 30%。30% 是下限。具体每批组数缺则 [A001]，禁止估算组数。\n\n## 5 现场动作提纲\n按计划取样 → 标识封志 → 共同送检 → 填委托单 → 检测机构核封志。试样损伤、超时、掉封不得当见证样。\n\n## 6 不合格升级\n样品或报告不合格：24 小时内上报，停止相关加工与使用，书面通知监理/建设，隔离待处置。本清单不代做复检结论。\n\n## 7 报告效力\n见证取样检测报告须加盖见证取样检测专用章。非建设单位委托的检测报告不得作为工程质量验收资料。出厂合格证不能替代见证送检。\n\n## 8 与配比、台账、仓管、资料的接口\n未复试或不合格的原材料，lab-mix 不得出施工配比；报告编号连续登记走 lab-record；实物隔离走 warehouse；资料目录走 supervision。\n\n## 9 禁令\n不写取样合格结论。不编检测数据。不把监督抽检、企业试验室自检、见证取样混成一种报告。\n\n{}\n",
        header("见证取样送检清单"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：SAC laboratory accreditation / BCA construction site records 只写标题。"),
            cn_only(&jur, "CN：见证取样和送检的规定 / 建设工程质量检测管理办法只写全名。建建〔2000〕211 号只列名称。"),
        ),
    );
    match ctx.write_md("取样送检清单.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn safety_brief(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let work = nonempty(&s(args, "work_item"), "待填。[A001]");
    let hazards = nonempty(&s(args, "hazards"), "待辨识");
    let controls = nonempty(&s(args, "controls"), "待填");
    let md = format!(
        "{}{banner}\n给现场技术员的讨论用交底草稿，不是工人口播，也不是签认件。须持证人员按正式文本复核签字后才可实施。\n\n## 1 封面\n工程名称待填。作业部位、工序待填。交底日期待填。交底人/接受人空栏。[A001]\n\n## 2 草稿声明\n须持证人员按正式文本复核签字后才可实施。\n\n## 3 作业部位与范围\n{work}\n\n轴线、楼层未给则 [A001]。禁止虚构图号。\n\n## 4 作业内容和工序步骤\n只列用户或方案里出现的步骤。未给则待填。[A001]\n\n## 5 危险源\n{hazards}\n\n只写本部位可能碰到的，不抄全集充数。\n\n## 6 防护要点\n{controls}\n\n栏杆、盖板、安全带挂点、通道、警戒。高度、间距、荷载一律 [A001]，不编毫米数。\n\n## 7 个人防护\n帽、鞋、镜、手套、安全带、呼吸防护。规格待填。[A001]\n\n## 8 禁止事项与喊停条件\n无防护不作业；酒后/带病不上高；有限空间未通风检测不进；指挥信号不清不起吊。\n\n## 9 应急要点\n就近撤离方向待填。急救原则：高坠不乱搬、触电先断电。报告对象待填。电话 [A001]。\n\n## 10 依据\n用户点名的规范全名。未提供文本则未核实表 + 条款 UNSPECIFIED。\n\n## 11 签字栏\n| 交底人 | 接受班组 | 安全员 | 日期 |\n| --- | --- | --- | --- |\n| （空） | （空） | （空） | 待填 |\n\n不预填姓名。本稿不下交底完毕结论。\n\n{}\n",
        header("安全交底草稿"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：WSH Council toolbox meeting 导则只写标题。"),
            cn_only(&jur, "CN：安全技术交底按专项方案实施程序只写标题，本岗不签认。"),
        ),
    );
    match ctx.write_md("安全交底草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn quality_checklist(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let lot = nonempty(&s(args, "inspection_lot"), "待填");
    let items = split_lines(&s(args, "items"));
    let main = if items.is_empty() {
        "| 检查内容 | 设计或标准要求 | 实测或观察 | 结果 | 处理意见 |\n| --- | --- | --- | --- | --- |\n| 待列主控项 [A001] | 待填 | 待填 | 未检 | （空） |".to_string()
    } else {
        let mut out = String::from("| 检查内容 | 设计或标准要求 | 实测或观察 | 结果 | 处理意见 |\n| --- | --- | --- | --- | --- |\n");
        for it in &items {
            out.push_str(&format!("| {it} | 待填 | 待填 | 未检 | （空） |\n"));
        }
        out
    };
    let gen = "| 检查内容 | 设计或标准要求 | 实测或观察 | 结果 | 处理意见 |\n| --- | --- | --- | --- | --- |\n| 待列一般项 [A001] | 待填 | 待填 | 未检 | （空） |";
    let hid = "| 检查内容 | 设计或标准要求 | 实测或观察 | 结果 | 处理意见 |\n| --- | --- | --- | --- | --- |\n| 待列隐蔽项 [A001] | 待填 | 待填 | 未检 | （空） |";
    let md = format!(
        "{}{banner}\n检验批、隐蔽验收、通病防治的检查栏目。不给合格结论，不替代监理组织验收。检验批：{lot}。\n\n## 1 封面与声明\n工程/楼栋/检验批部位待填。对应分项名称待填。检查表编号待填。[A001]\n\n## 2 划分说明\n本表覆盖哪一段、哪一层、哪一批待填。用户未给批量、抽样数量则 [A001]，不编最小抽样。\n\n## 3 进场与依据\n图纸图号仅用户清单。施工方案讨论稿名称待填。材料报告编号空则待填。禁止自造图号。\n\n## 4 主控项目检查栏\n{main}\n\n对安全、节能、环保和主要使用功能起决定作用的项。结果=未检。\n\n## 5 一般项目检查栏\n{gen}\n\n外观、尺寸偏差。同样不预填合格。结果=未检。\n\n## 6 隐蔽专项\n{hid}\n\n隐蔽前通知、影像、旁站记录栏目。未验收不建议进入下道，但不写开工令。\n\n## 7 通病防治核对\n楼板裂缝、填充墙裂缝、外墙/屋面/门窗渗漏、回填下沉、保护层、线管叠放、抹灰空鼓。只列易发部位和预防动作。\n\n## 8 不符合时的处理路径栏目\n返工返修后重新检查。检测鉴定、设计核算等路径只列名称，结论待有资质单位。\n\n## 9 资料闭合\n施工记录、测量、材料/试块报告与试验室台账是否对得上。缺报告写缺口，不编强度。\n\n## 10 签字栏\n| 质检员 | 工长 | 技术负责人 | 监理 |\n| --- | --- | --- | --- |\n| （空） | （空） | （空） | （空） |\n\n禁止预填同意验收。\n\n{}\n",
        header("质量检查表"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：CONQUAS 只写标题，不是本表评分。"),
            cn_only(&jur, "CN：建筑工程施工质量验收统一标准只写全名。条款 UNSPECIFIED。"),
        ),
    );
    match ctx.write_md("质量检查表.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn named_emergency_specials(blob: &str) -> Vec<&'static str> {
    let low = blob.to_lowercase();
    let mut named = Vec::new();
    let hints: &[(&str, &str)] = &[
        ("火灾", "火灾爆炸"),
        ("fire", "火灾爆炸"),
        ("爆炸", "火灾爆炸"),
        ("坠落", "高处坠落"),
        ("高处", "高处坠落"),
        ("打击", "物体打击"),
        ("坍塌", "坍塌"),
        ("触电", "触电"),
        ("起重", "起重机械"),
        ("有限空间", "中毒窒息/有限空间"),
        ("中毒", "中毒窒息/有限空间"),
        ("车辆", "车辆伤害"),
        ("疫情", "疫情或突发环境事件"),
    ];
    for (hint, spec) in hints {
        if low.contains(&hint.to_lowercase()) || blob.contains(hint) {
            if !named.contains(spec) {
                named.push(*spec);
            }
        }
    }
    named
}

fn emergency(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let scenario = nonempty(&s(args, "scenario"), "待填");
    let named = named_emergency_specials(&scenario);
    const SPECS: &[&str] = &[
        "高处坠落",
        "物体打击",
        "坍塌",
        "触电",
        "起重机械",
        "火灾爆炸",
        "中毒窒息/有限空间",
        "车辆伤害",
        "疫情或突发环境事件",
    ];
    let mut special = String::from("| 专项 | 本稿 |\n| --- | --- |\n");
    for spec in SPECS {
        if named.iter().any(|n| n == spec) {
            special.push_str(&format!("| {spec} | 本轮点名。只列名称，不展开假场景。 |\n"));
        } else {
            special.push_str(&format!("| {spec} | 常见名。用户未点名不展开。 |\n"));
        }
    }
    let md = format!(
        "{}{banner}\n只出目录、演练记录表头和待填附件。不签发预案。联系人通讯录全部 [A001]。情景：{scenario}。\n\n## 1 封面与声明\n单位/项目待填。预案名称待填。版本待填。签署人空栏。联系人通讯录全部 [A001]。\n\n## 2 编制说明\n风险辨识结论栏待填。应急资源调查清单栏：队伍、车辆、担架、灭火器、洗消、医院。无现场盘点不编数量。医院名称和电话待填。\n\n## 3 综合预案目录\n1. 组织机构与职责\n2. 预案体系\n3. 风险描述\n4. 预警与信息报告\n5. 响应分级\n6. 保障\n7. 培训演练与管理\n\n## 4 专项预案目录\n{special}\n用户没点名则只列常见名、不展开假场景。\n\n## 5 现场处置方案\n按场所：基坑、脚手架、配电房、食堂、宿舍、桩机区。含职责、措施、注意事项。未给场所则待填。\n\n## 6 应急处置卡\n一岗一卡，短步骤 + 联络人待填。电话 [A001]。\n\n## 7 信息报告\n内部升级顺序待填。向属地应急和行业主管部门报告的内容栏待填。不编已报告结论。\n\n## 8 演练计划与记录表头\n| 时间 | 科目 | 参演单位 | 评估人 | 发现问题 | 修订意见 |\n| --- | --- | --- | --- | --- | --- |\n| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |\n\n评估、问题、修订意见待填。本稿不下演练结论。\n\n## 9 附件\n| 附件 | 本稿 |\n| --- | --- |\n| 通讯录 | 待填；电话 [A001] |\n| 物资台账 | 待填 |\n| 医院路线 | 医院名称待填；电话 [A001] |\n| 周边告知 | 待填 |\n\n## 10 备案与评估节点\n公布日、拟备案机关、评估年待用户填。备案条件栏待核，本稿不下备案结论。\n\n## 11 禁令\n不编医院名称和电话，不编响应时间分钟数。有限空间救援强调禁止盲目进入。本稿不下演练通过结论。\n\n{}\n",
        header("应急预案提纲"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：SCDF Emergency Response Plan 只写标题。"),
            cn_only(&jur, "CN：生产安全事故应急预案管理办法只写标题。"),
        ),
    );
    match ctx.write_md("应急预案提纲.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn discipline_memo(ctx: &mut ToolCtx, args: &Value) -> String {
    let d = nonempty(&s(args, "discipline"), "本专业");
    let md = format!(
        "{}## 范围\n{}\n\n## 原则（不定参数则待填）\n待按提资填写。无计算书输入不定量。\n\n## 开放问题\n{}\n\n辖区规范不得静默混用。\n",
        header(&format!("{d}专业说明草稿")),
        nonempty(&s(args, "scope"), "待填"),
        nonempty(&s(args, "open_items"), "无"),
    );
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{md}{banner}条款 UNSPECIFIED。[A001]\n{}",
        sg_only(
            &jur,
            "禁止把中国大陆危大或施工规范族当作新加坡依据。SG：Building Control (Reportable Matters) Regulations 2025 只写标题。\n",
        ),
    );
    match ctx.write_md(&format!("{d}专业说明草稿.md"), &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn clash_minutes(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 专业\n{}\n\n## 问题清单\n{}\n\n每条须有责任专业与关闭条件。不改模型。{}\n",
        header("碰撞协调纪要"),
        nonempty(&s(args, "disciplines"), "待填"),
        nonempty(&s(args, "issues"), "待填"),
        sg_only(&jur, "SG：CORENET X / IFC+SG 只写标题，不是碰撞清零结论。"),
    );
    match ctx.write_md("碰撞协调纪要.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn qto_rules(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 过滤/扣减口径\n{}\n\n不编综合单价。{}\n",
        header("模型算量口径"),
        nonempty(&s(args, "filters"), "待填"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：IFC 基础数量 Qto_* 只写族名，不是结算依据。"),
            cn_only(&jur, "CN：工程量清单计价标准只写全名，不编综合单价。"),
        ),
    );
    match ctx.write_md("算量口径说明.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn parse_wbs_names(blob: &str) -> Vec<String> {
    let mut rows = Vec::new();
    for raw in blob.replace('；', "\n").replace(';', "\n").lines() {
        let mut t = raw.trim().to_string();
        if let Some(rest) = t.strip_prefix("写一份") {
            t = rest.trim().to_string();
        }
        if t.is_empty() || t == "草稿提纲" || t == "总进度计划" || t == "总控计划" || t == "master" {
            continue;
        }
        if t.starts_with('#') || t.starts_with("内部") {
            continue;
        }
        if t.chars().count() <= 80 {
            rows.push(t.chars().take(80).collect());
        }
    }
    rows
}

fn plan_skeleton(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let milestones = nonempty(&s(args, "milestones"), "");
    let level = nonempty(&s(args, "level"), "master");
    let blob = format!("{milestones}\n{level}");
    let names = parse_wbs_names(&blob);
    let wbs = if names.is_empty() {
        "| 编码 | 名称 | 责任单位 | 工程量来源 | 持续时间来源 | 紧前 |\n| --- | --- | --- | --- | --- | --- |\n| TBD | [A001] | TBD | 待填 | 待填 | 待填 |".to_string()
    } else {
        let mut out = String::from("| 编码 | 名称 | 责任单位 | 工程量来源 | 持续时间来源 | 紧前 |\n| --- | --- | --- | --- | --- | --- |\n");
        for n in &names {
            out.push_str(&format!("| TBD | {n} | TBD | 待填 | 待填 | 待填 |\n"));
        }
        out
    };
    let mile = if milestones.is_empty() || milestones == "待填" {
        "| 里程碑 | 日期 |\n| --- | --- |\n| 桩基完成 / ±0.000 / 主体封顶（候选） | 里程碑待填 |".to_string()
    } else {
        format!("| 里程碑 | 日期 |\n| --- | --- |\n| {milestones} | 待填 |")
    };
    let md = format!(
        "{}{banner}\n## 1 封面与文件控制\n层级：{level}。项目名称/合同工期待填。签认栏留空。[A001]\n\n## 2 草稿声明\n不是监理批准件，也不是可据以开工的进度计划。禁止编持续时间和关键线路。\n\n## 3 编制依据\n只列用户已给名称。无定额或方案则依据栏待补。条款 UNSPECIFIED。\n\n## 4 开竣工口径提示\n开竣工日期争议提示查阅法释〔2020〕25 号第八条、第九条认定顺序。本岗不代法院认定日期。\n\n## 5 工作分解\n{wbs}\n\nWBS。无图纸清单则工程量与持续时间一律待填。\n\n## 6 逻辑关系\n紧前、紧后、搭接类型（FS/SS/FF/SF）只写用户确认的工艺顺序。禁止编虚工作逻辑。\n\n## 7 一级网络与里程碑\n{mile}\n\n未给定的里程碑名称可列候选，日期待填。\n\n## 8 关键线路\n关键线路=待计算。用户未提供网络参数时禁止本稿指定。\n\n## 9 表达方式\n本稿出表头+文字逻辑，不假装已出批准用网络图。\n\n## 10 检查与基线\n冻结基线版本。总时差待计算。\n\n## 11 进度变更\n是否关键线路、对里程碑的影响待填。金额改召唤索赔调概（claim）。\n\n## 12 待填与禁令\n无来源数字写待填。禁止断言计划合理、一定能按期竣工。\n\n无定额不编人机料用量。{}\n",
        header("计划骨架"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：PSSCOC 工期条款只写族名。"),
            cn_only(&jur, "CN：施工组织设计规范只写全名，不编关键线路。"),
        ),
    );
    match ctx.write_md("计划骨架.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn compare_table(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let vendors = split_lines(&s(args, "vendors"));
    let mut md = format!(
        "{}{banner}\n标的：{}\n\n| 供应商 | 报价 | 工期 | 备注 |\n| --- | --- | --- | --- |\n",
        header("比价表草稿"),
        nonempty(&s(args, "item"), "待填")
    );
    if vendors.is_empty() {
        md.push_str("| 待询 | 无报价不编价 | TBD |  |\n");
    }
    for v in vendors {
        md.push_str(&format!("| {v} | 无报价不编价 | TBD |  |\n"));
    }
    md.push_str("\n[A001] 无报价不编价。");
    md.push_str(&sg_only(&jur, "SG：GeBIZ / MOF value for money 只写标题。"));
    md.push('\n');
    match ctx.write_md("比价表草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn purchase_plan(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let items = split_lines(&s(args, "items"));
    let mut md = format!("{}{banner}\n| 物资 | 甲指/自采 | 提前期 | 到货节点 |\n| --- | --- | --- | --- |\n", header("采购计划表"));
    for it in items {
        md.push_str(&format!("| {it} | 待划 | 待填 | 待填 |\n"));
    }
    md.push_str("\n[A001] 提前期待填。");
    md.push_str(&sg_only(&jur, "SG：BCA CRS 投标限额只写门户标题。"));
    md.push('\n');
    match ctx.write_md("采购计划表.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn extract_survey_points(blob: &str) -> Vec<String> {
    let re = regex::Regex::new(r"(?i)\b(?:CP|BM|PT|TP|GC|SP)[-_]?\d+[A-Za-z]?\b").expect("point re");
    let mut rows = Vec::new();
    for line in blob.lines() {
        let t = line.trim();
        if t.is_empty() || t.contains("用户未提供") {
            continue;
        }
        if t.contains("点号") || t.contains("控制点") || re.is_match(t) {
            rows.push(t.chars().take(200).collect());
        }
    }
    rows
}

fn extract_sensitive_jobs(blob: &str) -> Vec<String> {
    const KEYS: &[&str] = &[
        "危大",
        "临边",
        "基坑",
        "开挖",
        "起重",
        "脚手架",
        "模板",
        "有限空间",
        "拆除",
        "爆破",
        "高处",
        "PTW",
        "excavation",
        "lifting",
        "scaffold",
    ];
    let mut hits = Vec::new();
    for raw in blob.replace('；', "\n").replace(';', "\n").lines() {
        let t = raw.trim();
        if t.is_empty() {
            continue;
        }
        let lower = t.to_ascii_lowercase();
        if KEYS.iter().any(|k| t.contains(k) || lower.contains(&k.to_ascii_lowercase())) {
            hits.push(t.chars().take(120).collect());
        }
    }
    hits
}

fn gather_survey_blob(ctx: &ToolCtx, args: &Value) -> String {
    let mut parts = Vec::new();
    for key in [
        "known_points",
        "work_item",
        "text",
        "brief",
        "description",
        "points",
    ] {
        let v = s(args, key);
        if v.is_empty() || v == "用户未提供坐标/点号" || v == "待填作业" {
            continue;
        }
        parts.push(v);
    }
    for f in crate::attach::list_uploads(&ctx.paths, &ctx.session_id) {
        let Some(id) = f.get("id").and_then(|v| v.as_str()) else {
            continue;
        };
        if let Ok(body) = crate::attach::read_upload(&ctx.paths, &ctx.session_id, id, 0, 8_000) {
            parts.push(body);
        }
    }
    parts.join("\n")
}

fn dispatch_daily(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let progress = nonempty(&s(args, "progress"), "待填");
    let issues = nonempty(&s(args, "issues"), "待填");
    let blob = format!("{progress}\n{issues}");
    let jobs = extract_sensitive_jobs(&blob);
    let sensitive = if jobs.is_empty() {
        "- （本轮用户未点名敏感作业。判定仍交 method-hazard，本岗不判危大。）".to_string()
    } else {
        jobs.iter()
            .map(|j| format!("- {j}（只列名称；判定交 method-hazard）"))
            .collect::<Vec<_>>()
            .join("\n")
    };
    let md = format!(
        "{}{banner}\n## 1 报头\n待填项目/日期/班次。[A001]\n\n## 2 草稿声明\n{DISCLAIMER}\n\n## 3 计划接口\n无计划文件则整表待填，不编节点日期。[A001]\n\n## 4 当日实际\n{progress}\n\n## 5 人机料动态\n待按台账填写。[A001] 不编产量、工日、台班。\n\n## 6 指令栏\n下达人/接收人/内容空栏。签认空着。\n\n## 7 交叉作业与工作面交接\n用户说了才写。[A001]\n\n## 8 停复工与异常\n{issues}\n\n## 9 危大/高处/临边等敏感作业清单\n{sensitive}\n\n敏感作业只列名称与时段。是否危大、要否 PTW 交 method-hazard。本岗不签发。\n\n## 10 明日条件与待决策\n待填。[A001]\n\n## 11 附件表头\n旁站/交底/验收标识由用户确认，不替他们下合格结论。\n\n本日报不是调度令或工期承诺。{}\n",
        header("调度日报草稿"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：BCA construction site records 只写标题，本日报不是法定现场簿。"),
            cn_only(&jur, "CN：调度日报不是危大文件。"),
        ),
    );
    match ctx.write_md("调度日报草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn parse_subcontract_lines(blob: &str) -> Vec<(String, String, String)> {
    let qty_re = regex::Regex::new(r"(?i)(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>m2|m²|m3|t|吨|kg|工日|项)?").expect("qty re");
    let mut rows = Vec::new();
    for raw in blob.replace('；', "\n").replace(';', "\n").lines() {
        let mut t = raw.trim().to_string();
        if let Some(rest) = t.strip_prefix("写一份") {
            t = rest.trim().to_string();
        }
        if t.is_empty() || t == "待填分包" || t == "待计量" || t == "草稿提纲" {
            continue;
        }
        if t.starts_with('#') || t.starts_with("内部") {
            continue;
        }
        if let Some(m) = qty_re.find(&t) {
            let qty = qty_re.captures(&t).and_then(|c| c.name("qty")).map(|x| x.as_str().to_string()).unwrap_or_else(|| "TBD".into());
            let unit = qty_re.captures(&t).and_then(|c| c.name("unit")).map(|x| x.as_str().to_string()).unwrap_or_else(|| "TBD".into());
            let name = format!("{}{}", &t[..m.start()], &t[m.end()..]).trim_matches(|c: char| c == ' ' || c == '，' || c == ',').to_string();
            let name = if name.is_empty() { t.chars().take(80).collect() } else { name.chars().take(80).collect() };
            rows.push((name, unit, qty));
        } else if t.chars().count() <= 80 {
            rows.push((t.chars().take(80).collect(), "TBD".into(), "TBD".into()));
        }
    }
    rows
}

fn subcontract_sheet(ctx: &mut ToolCtx, args: &Value) -> String {
    let pkg = nonempty(&s(args, "package"), "");
    let qty_note = nonempty(&s(args, "qty_note"), "");
    let items = nonempty(&s(args, "items"), "");
    let blob = format!("{pkg}\n{qty_note}\n{items}");
    let parsed = parse_subcontract_lines(&blob);
    let table = if parsed.is_empty() {
        "| 分项 | 单位 | 数量 | 合同单价 | 合价 | 来源 |\n| --- | --- | --- | --- | --- | --- |\n| [A001] | TBD | TBD | TBD | TBD | 用户未给细目 |".to_string()
    } else {
        let mut out = String::from("| 分项 | 单位 | 数量 | 合同单价 | 合价 | 来源 |\n| --- | --- | --- | --- | --- | --- |\n");
        for (n, u, q) in parsed {
            out.push_str(&format!("| {n} | {u} | {q} | TBD | TBD | 用户细目 |\n"));
        }
        out
    };
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 1 封面与草稿声明\n内部对下结算讨论稿，不是已生效结算协议。无总包/业主确认不编金额。\n\n## 2 合同关系\n专业分包或劳务分包待用户指定。禁止把违法转包写成合法分包。合同编号/计价方式待贴。[A001]\n\n## 3 本期完成\n{table}\n\n量只抄用户任务单或实测。禁止用形象百分比空估。对上未批则本期待填。\n\n## 4 合同内价款栏\n数量 × 合同单价。无合同单价、无总包/业主确认则合价 TBD。\n\n## 5 合同外\n洽商、签证另表。无签认不进结算。\n\n## 6 扣款表头\n| 扣款项 | 金额 |\n| --- | --- |\n| 甲供材领用 / 水电 / 周转料具损坏 | TBD |\n| 质量/安全罚款（须书面通知） | TBD |\n| 预付款抵扣 / 前期末扣清 | TBD |\n| 其他 | TBD |\n\n没有凭证不编扣款。\n\n## 7 质量与质保\n缺陷责任期内预留质量保证金。预留比例待按建质〔2017〕138 号与用户合同核对，不另编百分比当结算结论。\n\n## 8 农民工工资专节\n| 栏 | 金额 |\n| --- | --- |\n| 应付人工费 | TBD |\n| 应付分包工程款 | TBD |\n\n两栏分列，不混。\n\n## 9 会签栏\n| 部门 | 意见 |\n| --- | --- |\n| 现场工长核量 | 未会签 |\n| 工程部 / 安质 / 物资 / 商务 | 未会签 |\n| 项目经理 | 未会签 |\n\n## 10 与对上验工、财务接口\n对下累计原则上不超过对上已计价对应份额。付款申请交 finance-fund，发票税目交 finance-tax。\n\n## 11 自检\n无编造工日单价。本表不下发放结论。\n\n{}\n",
        header("分包结算表头"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：PSSCOC Nominated Sub-Contract / SOP Act 只写全名。"),
            cn_only(&jur, "CN：保障农民工工资支付条例只写全名，金额 TBD。"),
        ),
    );
    match ctx.write_md("分包结算表头.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn geotech_brief(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 范围\n{}\n\n## 已知\n{}\n\n## 口径\n- 无地勘/用户参数不填承载力、水位、c/φ。\n- [A001] 未提供的岩土参数一律待填。\n- 规范只写全名，条款 UNSPECIFIED。\n{}\n本提纲不是勘察报告签认件。\n",
        header("岩土勘察提纲"),
        nonempty(&s(args, "scope"), "待填"),
        nonempty(&s(args, "known_facts"), "（用户未提供）"),
        format!(
            "{}{}",
            sg_only(&jur, "- SG：SS EN 1997 / GeoSS / Pre-Construction Survey / AGS(SG) 只写标题。"),
            cn_only(&jur, "- CN：岩土勘察规范只写全名。"),
        ),
    );
    match ctx.write_md("岩土勘察提纲.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn lookahead_skip(t: &str) -> bool {
    matches!(
        t,
        "草稿提纲"
            | "总进度计划"
            | "总控计划"
            | "周计划"
            | "月计划"
            | "四周滚动"
            | "周月计划"
            | "四周滚动计划"
            | "master"
            | "lookahead"
            | "制约已清"
            | "条件已具备"
            | "待填"
            | "四周"
            | "第1–4周"
            | "第1-4周"
    ) || (t.starts_with('第') && t.contains('周'))
}

fn lookahead_blocked(t: &str) -> bool {
    const MARK: &[&str] = &["未清", "未到", "未交", "无图", "未发", "过期"];
    if MARK.iter().any(|m| t.contains(m)) {
        return true;
    }
    if t.contains("制约已清") || t.contains("条件已具备") {
        return false;
    }
    t.contains("制约")
}

fn clean_lookahead_job(t: &str) -> String {
    t.replace("制约已清", "")
        .replace("条件已具备", "")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .trim_matches(|c: char| c == ' ' || c == '，' || c == ',' || c == ';' || c == '；')
        .to_string()
}

fn parse_lookahead(blob: &str) -> (Vec<String>, Vec<String>, bool) {
    let any_cleared = blob.contains("制约已清") || blob.contains("条件已具备");
    let mut jobs: Vec<String> = Vec::new();
    let mut blocked: Vec<String> = Vec::new();
    for raw in blob.replace('；', "\n").replace(';', "\n").lines() {
        let mut t = raw.trim().to_string();
        if let Some(rest) = t.strip_prefix("写一份") {
            t = rest.trim().to_string();
        }
        if t.is_empty() || lookahead_skip(&t) {
            continue;
        }
        if t.starts_with('#') || t.starts_with("内部") {
            continue;
        }
        if t.chars().count() > 80 {
            t = t.chars().take(80).collect();
        }
        let name = {
            let c = clean_lookahead_job(&t);
            if c.is_empty() {
                t.clone()
            } else {
                c
            }
        };
        if name.is_empty() || lookahead_skip(&name) {
            continue;
        }
        if lookahead_blocked(&t) {
            blocked.push(name);
        } else if !jobs.iter().any(|j| j == &name) {
            jobs.push(name);
        }
    }
    let can_promise = any_cleared && blocked.is_empty() && !jobs.is_empty();
    (jobs, blocked, can_promise)
}

fn plan_lookahead(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let window = nonempty(&s(args, "window"), "待填");
    let constraints = s(args, "constraints");
    let works = s(args, "works");
    let blob = format!("{window}\n{constraints}\n{works}");
    let (jobs, blocked, can_promise) = parse_lookahead(&blob);
    let week_jobs = if jobs.is_empty() {
        "待填 [A001]".to_string()
    } else {
        jobs.join("；")
    };
    let week_block = if !blocked.is_empty() {
        blocked.join("；")
    } else if can_promise {
        "无未清制约".to_string()
    } else {
        "制约未清".to_string()
    };
    let four = format!(
        "| 周次 | 粒度 | 作业 | 制约状态 |\n| --- | --- | --- | --- |\n| 第1周 | 班组、工作面、日顺序 | {week_jobs} | {week_block} |\n| 第2周 | 分项与责任人 | {week_jobs} | {week_block} |\n| 第3周 | 分项与制约（较粗） | {week_jobs} | {week_block} |\n| 第4周 | 分项与制约（较粗） | {week_jobs} | {week_block} |"
    );
    let cons = if blocked.is_empty() {
        "| 工作 | 制约 | 责任人 | 计划清除日 |\n| --- | --- | --- | --- |\n| [A001] | 待填 | 待填 | 待填 |".to_string()
    } else {
        let mut out = String::from("| 工作 | 制约 | 责任人 | 计划清除日 |\n| --- | --- | --- | --- |\n");
        for n in &blocked {
            out.push_str(&format!("| {n} | 未清 | 待填 | 待填 |\n"));
        }
        out
    };
    let (promise_note, promise) = if can_promise {
        let mut tbl = String::from("| 作业 | 认领人 | 周末兑现 |\n| --- | --- | --- |\n");
        for n in &jobs {
            tbl.push_str(&format!("| {n} | 待填 | 待对照 |\n"));
        }
        ("只列入用户已标明条件已具备的工作。工长认领栏待填。", tbl)
    } else {
        (
            "制约未清，不得写入本周承诺。",
            "| 作业 | 认领人 | 周末兑现 |\n| --- | --- | --- |\n| （空） | — | — |".to_string(),
        )
    };
    let named = if jobs.is_empty() {
        String::new()
    } else {
        format!("\n本轮点名作业：{}\n", jobs.join("；"))
    };
    let md = format!(
        "{}{banner}\n必须挂在总控里程碑下。禁止用周计划改合同工期。不是工期签证，不是复工许可。窗口：{window}。\n\n## 1 封面\n计划期（哪四周或哪一自然月）待填。对应总控版本号待填。编制人栏空。内部讨论草稿。[A001]\n\n## 2 从总控抽取窗口\n把总控里落在未来约四周的工作拉到工长能认领的粒度。总控没有该窗口的工作，本栏写待补，不要发明作业。{named}\n## 3 近细远粗\n{four}\n\n第 1 周量化到班组、工作面、日顺序；第 2 周到分项与责任人；第 3–4 周保留分项与制约，允许较粗。不编持续天数。\n\n## 4 制约因素\n{cons}\n\n每条制约指定责任人和计划清除日。未清项不得列入第 5 节周承诺。\n\n## 5 周承诺\n{promise_note}\n\n{promise}\n\n周末对照承诺兑现（完成项 / 承诺项）。未完成只记原因分类（图、料、人、机、面、天气、指令），不写处罚结论。\n\n## 6 交叉作业\n同一工作面或上下立体空间有两个及以上专业时，单列交叉窗口：谁先谁后、防护谁做、吊装禁区、噪音时段。计划只排窗口。安全措施改召唤安全交底或施工方案，不在本稿编栏杆高度或吊装半径。\n\n## 7 停工条件\n本月可能触发暂停的外部条件，日期待填：大风、暴雨暴雪、能见度不足、高温橙色以上、冬期测温未达标、台风预警、政府停工令、危大方案未论证、特种设备证件过期。停工后只列复工条件栏。本岗不签发复工许可，不编风速限值。\n\n## 8 与总控的回写\n本周若拖的是关键工作或吃完总时差，必须回写总控版本，并提示索赔调概看时限。非关键工作的小调整可留在四周窗口内，纪要写明未改总工期。\n\n## 9 月度形象对照\n| 形象部位 | 计划形象 | 实际形象 | 偏差天数 | 原因 | 纠偏 |\n| --- | --- | --- | --- | --- | --- |\n| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |\n\n无现场反馈则实际栏待填。不要把照片描述写成已验收合格。\n\n## 10 待填与禁令\n无班组名单、无总控版本、无制约责任人，对应整节待填。禁止断言本周计划必定兑现、交叉作业已安全、停工后即可实施。\n\n{}\n",
        header("周月计划骨架"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：Last Planner lookahead 只写方法名，不是合同工期变更。"),
            cn_only(&jur, "CN：周月计划不是工期签证。"),
        ),
    );
    match ctx.write_md("周月计划骨架.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn interim_measure(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let period = nonempty(&s(args, "period"), "待填");
    let qty_note = nonempty(&s(args, "qty_note"), "");
    let items = nonempty(&s(args, "items"), "");
    let blob = format!("{qty_note}\n{items}");
    let parsed = parse_subcontract_lines(&blob);
    let table = if parsed.is_empty() {
        "| 清单编码 | 名称 | 单位 | 合同量 | 上期末开累 | 本期申报 | 监理审 | 业主核 | 单价 | 本期价 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n| TBD | [A001] | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |".to_string()
    } else {
        let mut out = String::from("| 清单编码 | 名称 | 单位 | 合同量 | 上期末开累 | 本期申报 | 监理审 | 业主核 | 单价 | 本期价 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n");
        for (n, u, q) in parsed {
            out.push_str(&format!("| TBD | {n} | {u} | TBD | TBD | {q} | TBD | TBD | TBD | TBD |\n"));
        }
        out
    };
    let md = format!(
        "{}{banner}\n## 1 封面与草稿声明\n内部报审讨论稿，不是已核准验工报表，不是付款指令。无业主确认不编本期应付。\n\n## 2 原则\n有实物工作量的先验工、后计价。不合格、未履行变更程序、超出合同的，不予计价。\n\n## 3 本期范围\n期次：{period}。开累与本期分列。起止日期待填。[A001]\n\n## 4 计量依据\n已标价清单及计算规则；经审核施工图及批准变更；质量合格证明。条款原文待贴。\n\n## 5 计量草表\n{table}\n\n监理审、业主核、单价、本期价无确认则 TBD。不编应付合价。\n\n## 6 变更、物价、索赔\n只列入已批准文件对应金额或「已批文号 + 金额待填」。未批变更不得计价。\n\n## 7 过程结算与进度款\n预付款 / 进度款 / 竣工结算只写财建〔2004〕369 号全名。进度款比例待按财建〔2022〕183 号与用户合同核对，不另编百分比。\n\n## 8 农民工工资列示\n| 栏 | 金额 |\n| --- | --- |\n| 用于支付农民工工资的工程款 | TBD |\n\n## 9 扣减与预留\n| 项 | 金额 |\n| --- | --- |\n| 预付款抵扣 / 甲供材 / 质保金 / 违约金 | TBD |\n\n有合同和凭证才列。\n\n## 10 不予计价警示\n无开工报告、质量不合格、超图未变、重复计量、超前报量且长期未实施：本期不计价。不作指控。\n\n## 11 报审签认\n承包人编制 → 监理审核 → 建设单位核准。缺一环不写付款结论。\n\n## 12 自检\n无业主确认不编应付合价。价税分开表头保留。\n\n{}\n",
        header("验工计价草稿"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：Security of Payment Act payment claim 只写标题，时限 UNSPECIFIED。"),
            cn_only(&jur, "CN：验工计价按用户合同，金额 TBD。"),
        ),
    );
    match ctx.write_md("验工计价草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn structure_calc(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 体系\n{}\n\n## 开放问题\n{}\n\n## 口径\n- 无用户荷载、材料、跨度则不定构件尺寸。\n- [A001] 强度、配筋、地基参数待填。\n- 规范只写全名，条款 UNSPECIFIED。\n{}\n本提纲不是计算书签认件。\n",
        header("结构计算书提纲"),
        nonempty(&s(args, "system"), "待填"),
        nonempty(&s(args, "open_items"), "无"),
        format!(
            "{}{}",
            sg_only(&jur, "- SG：SS EN 族名 / Accredited Checker / Structural Plan 只写标题。"),
            cn_only(&jur, "- CN：混凝土结构设计标准只写全名。"),
        ),
    );
    match ctx.write_md("结构计算书提纲.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn survey_record(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let item = nonempty(&s(args, "work_item"), "待填作业");
    let blob = gather_survey_blob(ctx, args);
    let copied = extract_survey_points(&blob);
    let known = if copied.is_empty() {
        "| 点号 | 东坐标 | 北坐标 | 高程 | 来源 |\n| --- | --- | --- | --- | --- |\n| [A001] | [A001] | [A001] | [A001] | 用户未给 |".to_string()
    } else {
        copied
            .iter()
            .map(|p| format!("- {p}"))
            .collect::<Vec<_>>()
            .join("\n")
    };
    let md = format!(
        "{}{banner}\n## 1 封面与文件控制\n空签认栏。内部讨论草稿。\n\n## 2 草稿与责任声明\n{DISCLAIMER}\n\n## 3 任务范围与部位\n{item}\n\n## 4 已知起算\n{known}\n\n禁止编造坐标或点号。无用户坐标不编点号。\n\n## 5 控制网与加密\n方法名称由用户定。[A001]\n\n## 6 放样内容\n图号必须来自用户清单。[A001]\n\n## 7 竖向传递\n无图纸不指定孔位。[A001]\n\n## 8 复测与检核\n闭合差栏待填。不写复测合格。\n\n## 9 仪器与人员\n证书编号待填。[A001]\n\n## 10 停测与异常\n点位破坏/超限升级路径待填。\n\n## 11 附录\n点之记/观测手簿表头。无数据不填示范数。\n\n- [A001] 未提供的坐标、高程、闭合差一律待填。\n- 规范只写全名，条款 UNSPECIFIED。\n{}\n本记录不是复测签认件，不可以当作施工依据。\n",
        header("测量记录口径"),
        format!(
            "{}{}",
            sg_only(&jur, "- SG：SVY21 / SHD 只写坐标系统名，无用户坐标不编点号。"),
            cn_only(&jur, "- CN：工程测量标准只写全名。"),
        ),
    );
    match ctx.write_md("测量记录口径.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn parse_wh_rows(blob: &str) -> Vec<(String, String, String)> {
    let mut rows = Vec::new();
    for raw in blob.replace('；', "\n").replace(';', "\n").lines() {
        let mut t = raw.trim().to_string();
        if let Some(rest) = t.strip_prefix("写一份") {
            t = rest.trim().to_string();
        }
        if t.is_empty()
            || matches!(
                t.as_str(),
                "草稿提纲" | "收发存" | "收发存台账" | "仓管" | "待填" | "SG" | "CN"
            )
        {
            continue;
        }
        if t.starts_with('#') || t.starts_with("内部") {
            continue;
        }
        let (mut name, qty, _) = split_resource_qty(&t);
        for key in ["入库", "进场", "出库", "领料", "盘点", "实存"] {
            name = name.replace(key, "");
        }
        name = name.split_whitespace().collect::<Vec<_>>().join(" ");
        if name.is_empty() {
            name = t.chars().take(80).collect();
        }
        let mut inbound = "TBD".to_string();
        let mut outbound = "TBD".to_string();
        if t.contains("出库") || t.contains("领料") {
            if qty != "TBD" {
                outbound = qty;
            }
        } else if t.contains("入库") || t.contains("进场") {
            if qty != "TBD" {
                inbound = qty;
            }
        } else if qty != "TBD" {
            inbound = qty;
        }
        rows.push((name, inbound, outbound));
    }
    rows
}

fn warehouse_log(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let item = s(args, "item");
    let note = nonempty(&s(args, "note"), "待填");
    let blob = format!("{item}\n{note}");
    let has_count = blob.contains("盘点") || blob.contains("实存");
    let rows = parse_wh_rows(&blob);
    let (short, full) = if rows.is_empty() {
        (
            "| 物资 | 入库 | 出库 | 结存 | 备注 |\n| --- | --- | --- | --- | --- |\n| 待填物资 | TBD | TBD | TBD | 待填 |".to_string(),
            "| 物资 | 规格批次 | 单位 | 期初 | 入库 | 出库 | 账面结存 | 盘点实存 | 差异 | 来源单据号 | 单价 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n| 待填物资 | 待填 | 待填 | TBD | TBD | TBD | TBD | TBD | TBD | 待填 | TBD |".to_string(),
        )
    } else {
        let mut short = String::from("| 物资 | 入库 | 出库 | 结存 | 备注 |\n| --- | --- | --- | --- | --- |\n");
        let mut full = String::from("| 物资 | 规格批次 | 单位 | 期初 | 入库 | 出库 | 账面结存 | 盘点实存 | 差异 | 来源单据号 | 单价 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n");
        for (n, inn, out) in &rows {
            short.push_str(&format!("| {n} | {inn} | {out} | TBD | {note} |\n"));
            full.push_str(&format!("| {n} | 待填 | 待填 | TBD | {inn} | {out} | TBD | TBD | TBD | 待填 | TBD |\n"));
        }
        (short, full)
    };
    let count_note = if has_count {
        "有盘点栏。账、卡、物三栏和差异原因待现场填写。未签字确认不得向现场材料提供盈亏数。"
    } else {
        "[A001] 无盘点不编盈亏。"
    };
    let md = format!(
        "{}{banner}\n内部讨论，不替代正式入库单签认，不替代财务记账，不给材料合格结论。\n\n## 1 草稿声明\n内部讨论。不替代正式入库单签认，不替代财务记账，不给材料合格结论。\n\n## 2 库区与分类\n合格区、待检区、不合格隔离区分开。甲指、甲限、自采分堆分账。危险品单独库位。本岗不编间距米数。\n\n## 3 入库验收\n对照采购订单或送货单核名称、规格、数量、批次、外观。需复试的材料进待检区，试验报告未出不得当作合格料发放。实收与应收差异记数量，不涂改凑平。\n\n## 4 标识与保管\n每垛标明名称、规格、批次、进场日期、状态（合格 / 待检 / 不合格）。不擅自报废数字。\n\n## 5 限额领料出库\n必须凭限额领料单。无单不发料。超限额走追加审批，不口头超发。\n\n## 6 盘点\n{count_note}\n\n至少月清。账物不符先记差异，禁止改台账凑数。[A001] 无盘点不编盈亏。\n\n## 7 收发存表头\n{short}\n\n{full}\n\n有数只抄用户原文。无数 TBD。单价无询价或合同价则 TBD。FIFO 不是法定检定周期。\n\n## 8 危险品台账\n| 物资 | 入库 | 领用 | 退回 | 结存 | 双人复核 |\n| --- | --- | --- | --- | --- | --- |\n| 待填 | TBD | TBD | TBD | TBD | 待填 |\n\n消防间距和存储限量以用户平面和安质环要求为准，本岗不编间距米数。\n\n## 9 禁令\n不把待检料写成已合格。不给复试合格结论。不编定额章节和综合单价。塔吊证件交设备管理岗。\n\n{}\n",
        header("收发存台账口径"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：Factory Notification 不是损耗公式。"),
            cn_only(&jur, "CN：收发存台账不是特种设备检定周期。"),
        ),
    );
    match ctx.write_md("收发存台账.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn pack_ship_list() -> String {
    "pack-ship__list\npack-ship__plan\npack-ship__export\nutilization/can_fit/mid50/系固待办 只抄 solver；未接通写 UNSPECIFIED。".into()
}

fn _copy_solver_field(solver: &Value, keys: &[&str]) -> String {
    for k in keys {
        if let Some(v) = solver.get(*k) {
            if v.is_null() {
                continue;
            }
            if let Some(s) = v.as_str() {
                if !s.is_empty() {
                    return s.to_string();
                }
            } else {
                return v.to_string();
            }
        }
    }
    "UNSPECIFIED".into()
}

fn pack_ship_export(args: &Value) -> String {
    let connected = args.get("connected").and_then(|v| v.as_bool());
    let solver = args.get("solver").cloned().unwrap_or(json!({}));
    let disconnected = connected == Some(false) || !solver.is_object() || solver.as_object().map(|o| o.is_empty()).unwrap_or(true);
    let util = if disconnected {
        "UNSPECIFIED".into()
    } else {
        _copy_solver_field(&solver, &["utilization", "util", "volume_util"])
    };
    let can_fit = if disconnected {
        "UNSPECIFIED".into()
    } else {
        _copy_solver_field(&solver, &["can_fit"])
    };
    let mid50 = if disconnected {
        "UNSPECIFIED".into()
    } else {
        _copy_solver_field(&solver, &["mid50", "mass_in_mid50_ratio"])
    };
    let lash = if disconnected {
        "UNSPECIFIED".into()
    } else {
        _copy_solver_field(&solver, &["系固待办", "lashing_todo"])
    };
    format!(
        "pack-ship__export\nutilization={util}\ncan_fit={can_fit}\nmid50={mid50}\n系固待办={lash}\nxyz=UNSPECIFIED\n"
    )
}

fn pack_ship_plan(ctx: &mut ToolCtx, args: &Value) -> String {
    let mut materials = nonempty(&s(args, "materials"), "");
    if materials.is_empty() {
        for f in crate::attach::list_uploads(&ctx.paths, &ctx.session_id) {
            let Some(id) = f.get("id").and_then(|v| v.as_str()) else {
                continue;
            };
            if let Ok(body) = crate::attach::read_upload(&ctx.paths, &ctx.session_id, id, 0, 8_000) {
                materials.push_str(&body);
                materials.push('\n');
            }
        }
    }
    let materials = nonempty(&materials, "未提供物料表");
    let project = nonempty(&s(args, "project_name"), "未命名发运");
    let notes = s(args, "notes");
    let (jur, banner) = zone_banner(args);
    let force_off = args.get("connected").and_then(|v| v.as_bool()) == Some(false);
    let solver = args.get("solver").cloned().unwrap_or(json!({}));
    let solver_empty = solver.as_object().map(|o| o.is_empty()).unwrap_or(true);
    let disconnected = force_off || solver_empty;
    let four = if disconnected {
        pack_ship_export(&json!({"connected": false}))
    } else {
        pack_ship_export(&json!({"connected": true, "solver": solver}))
    };
    let tool_block = if force_off {
        format!(
            "## packing-agent 回传（工具计算，非本岗编造）\n\n未接通 solver 快照。\n\n```\n{four}```\n"
        )
    } else {
        let agent = crate::websearch::run_blocking(|| crate::packing_bridge::run(&materials, &notes));
        format!(
            "## packing-agent 回传（工具计算，非本岗编造）\n\n{}\n\n```\n{four}```\n",
            agent.markdown()
        )
    };
    let n0_line = if disconnected {
        "柜数 N0* = UNSPECIFIED；摆位 xyz = UNSPECIFIED。"
    } else {
        "柜数/N0* 以上文工具回传为准；未出现的数字标 UNSPECIFIED。"
    };
    let md = format!(
        "{}{banner}\n## 工程/批次\n{project}\n\n## 用户物料（只抄原文）\n{materials}\n\n{tool_block}\n## 口径\n- 官方作业守则标题：IMO/ILO/UNECE Code of Practice for Packing of Cargo Transport Units (**CTU Code**, 2014)。非强制性全球作业守则；条款 UNSPECIFIED。https://www.imo.org/en/ourwork/safety/pages/ctu-code.aspx\n- CSC（International Convention for Safe Containers）Safety Approval Plate 有效性由持证人员核，本表不判柜况。\n- 数值边界：与 packing-agent 相同——**工具算数，模型只编排**。禁止在本表手写坐标。\n- {n0_line}\n- [A001] 单件尺寸/重量未给则待填。\n{}\n本作业单不是订舱承诺，不是危险品申报。\n",
        header(&format!("{project} · 装箱拼柜作业单")),
        sg_only(&jur, "- SG：港口/码头作业另对 MPA / PSA 现场规定；本表不编申报号。\n"),
    );
    match ctx.write_md("装箱作业单.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn pack_ship_health() -> String {
    crate::packing_bridge::probe().to_string()
}

fn env_list(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let site = nonempty(&s(args, "site"), "待填工地");
    let issues = nonempty(&s(args, "issues"), "扬尘 / 噪声 / 弃土（待辨识）");
    let md = format!(
        "{}{banner}\n覆盖扬尘、弃土、污水、噪声/夜间施工、市容围挡。不是排污许可，也不是城管销号证明。工地：{site}。事项：{issues}。\n\n## 1 封面\n项目、标段、清单日期、责任人空栏、属地区县待填。[A001]\n\n## 2 声明\nAI 草稿。措施落实与是否达标由现场和属地监管确认。\n\n## 3 扬尘\n| 项 | 措施栏 | 限值 |\n| --- | --- | --- |\n| 扬尘 | 围挡、道路硬化冲洗、裸土覆盖、粉料入库存罐 | UNSPECIFIED |\n| 弃土 | 分类堆放、联单或核准去向待填 | UNSPECIFIED |\n| 污水 | 沉淀/洗车台排水去向待填，不得直排 | UNSPECIFIED |\n| 夜间 | 属地夜间限制段待核，连续作业报批单另附 | UNSPECIFIED |\n| 市容 | 大门、公示牌、堆码、人车分流 | UNSPECIFIED |\n\n风速阈值用户给才写。无监测数据不编 dB 或浓度。[A001]\n\n## 4 弃土与建筑垃圾\n产生部位、暂存点、分类、运输单位、消纳单位、联单编号全部待填。\n\n## 5 污水与泥浆\n沉淀池/洗车台排水去向待填。不得直排市政管或河道。容量、排放口编号待填。\n\n## 6 噪声与夜间\n昼间/夜间作业时段以属地公告为准。敏感点距离用户给才写。限值 UNSPECIFIED。\n\n## 7 文明施工市容\n大门、公示牌、材料堆码、人员通道与车辆分流。\n\n## 8 与商务接口\n安全文明施工费、扬尘防治增加费只列措施事实。费率 TBD，交商务。\n\n## 9 停工与升级\n重污染天气、大风、投诉、执法检查——列接到哪一级指令停哪一类作业。本岗不下停工令。\n\n## 10 签字栏\n| 环保员 | 生产经理 | 资料员 |\n| --- | --- | --- |\n| （空） | （空） | （空） |\n\n本清单不是排放许可。\n\n{}\n",
        header("环保文明清单"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：NEA Construction Noise Control / Sundays and PH / Noise Management Plan；PUB Earth Control Measures。只列标题，限值 UNSPECIFIED。"),
            cn_only(&jur, "CN：噪声法/扬尘口径只列名称。不编 TSP 限值。"),
        ),
    );
    match ctx.write_md("环保文明清单.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn parse_equip_names(blob: &str) -> Vec<String> {
    let mut rows = Vec::new();
    for raw in blob.replace('；', "\n").replace(';', "\n").lines() {
        let mut t = raw.trim().to_string();
        if let Some(rest) = t.strip_prefix("写一份") {
            t = rest.trim().to_string();
        }
        for key in ["合格证", "使用登记", "作业人员证件", "作业证"] {
            if let Some(pos) = t.find(key) {
                t = t[..pos].trim().to_string();
            }
        }
        if t.is_empty()
            || matches!(t.as_str(), "草稿提纲" | "设备台账" | "维保计划" | "待填" | "MOM" | "SG" | "CN")
        {
            continue;
        }
        if t.starts_with('#') || t.starts_with("内部") {
            continue;
        }
        if t.chars().count() > 80 {
            t = t.chars().take(80).collect();
        }
        if !rows.iter().any(|n| n == &t) {
            rows.push(t);
        }
    }
    rows
}

fn copy_equip_certs(blob: &str) -> Vec<(String, String)> {
    let mut out = Vec::new();
    let keys = ["合格证", "使用登记", "作业人员证件", "作业证"];
    for key in keys {
        if let Some(pos) = blob.find(key) {
            let rest = blob[pos + key.len()..].trim_start_matches([':', '：', ' ', '\t']);
            let token: String = rest
                .chars()
                .take_while(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_' || *c == '.' || *c == '/')
                .collect();
            if token.chars().count() >= 3 {
                out.push((key.to_string(), token));
            }
        }
    }
    out
}

fn equip_ledger(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let blob = format!("{}\n{}", s(args, "equipment"), s(args, "certs"));
    let names = parse_equip_names(&s(args, "equipment"));
    let certs = copy_equip_certs(&blob);
    let cert_cell = if certs.is_empty() {
        "特种设备证件待核".to_string()
    } else {
        certs
            .iter()
            .map(|(n, c)| format!("{n} {c}（用户给定）"))
            .collect::<Vec<_>>()
            .join("；")
    };
    let inv = if names.is_empty() {
        "| 名称 | 规格型号 | 厂编号或备案号 | 自有或租赁 | 计划进退场 | 当前状态 |\n| --- | --- | --- | --- | --- | --- |\n| [A001] | 待填 | 待填 | 待填 | 待填 | 待进场 |".to_string()
    } else {
        let mut t = String::from("| 名称 | 规格型号 | 厂编号或备案号 | 自有或租赁 | 计划进退场 | 当前状态 |\n| --- | --- | --- | --- | --- | --- |\n");
        for n in &names {
            t.push_str(&format!("| {n} | 待填 | 待填 | 待填 | 待填 | 待进场 |\n"));
        }
        t
    };
    let gate = if names.is_empty() {
        format!("| 设备 | 进场验收 | 证件 | 维保 |\n| --- | --- | --- | --- |\n| 待填 | 待做 | {cert_cell} | 待排 |")
    } else {
        let mut t = String::from("| 设备 | 进场验收 | 证件 | 维保 |\n| --- | --- | --- | --- |\n");
        for n in &names {
            t.push_str(&format!("| {n} | 待做 | {cert_cell} | 待排 |\n"));
        }
        t
    };
    let cert_tbl = if certs.is_empty() {
        "| 证书名称 | 编号 | 有效期 | 作业项目 | 状态 |\n| --- | --- | --- | --- |\n| 产品合格证 | 待核 | 待填 | 待填 | 待核 |\n| 使用登记 | 待核 | 待填 | 待填 | 待核 |\n| 作业人员证件 | 待核 | 待填 | 待填 | 待核 |".to_string()
    } else {
        let mut t = String::from("| 证书名称 | 编号 | 有效期 | 作业项目 | 状态 |\n| --- | --- | --- | --- |\n");
        for (n, c) in &certs {
            t.push_str(&format!("| {n} | {c} | 待填 | 待填 | 用户给定 |\n"));
        }
        t
    };
    let md = format!(
        "{}{banner}\n内部讨论。不构成特种设备使用登记、安装验收签认、法定专项方案或开工依据。签认栏留空。\n\n## 1 封面与草稿声明\n标明内部讨论。签认栏留空。[A001]\n\n## 2 设备清单表头\n{inv}\n\n无用户清单不编造机号和备案号。只抄用户设备名。\n\n## 3 进场验收\n{gate}\n\n[A001] 无证件不编进场结论。缺一件写不得进场。本岗不签发使用登记。\n\n## 4 租赁与台班\n合同要素：谁负责安拆、顶升附着、维保和检测费用；按台班还是包月。无报价则租金和合价 TBD。\n\n## 5 维保计划\n按台分列日常点检、定期保养、故障修理。顶升和附着单独留栏。写过计划不等于已经保养，完成记录栏待填。\n\n## 6 证件与检验台账\n{cert_tbl}\n\n只抄用户已给证件。过期视同缺失。不编证号。\n\n## 7 退场与结算附件目录\n进退场单、台班单、维保和修理记录、检测报告复印件、租赁补充协议。金额待填。\n\n## 8 资料目录\n资料目录交给资料监理专家闭合。本岗不宣称资料已闭合。安装拆卸方案交施工方案；是否危大交 method-hazard。\n\n## 9 禁令\n不签发使用登记。不编租金、折旧率和综合单价。不宣称通过专家论证或可以投入使用。\n\n{}\n",
        header("设备台账口径"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：MOM lifting equipment / approved crane contractor 只写标题。"),
            cn_only(&jur, "CN：特种设备安全法只写全名。"),
        ),
    );
    match ctx.write_md("设备台账.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn fund_plan(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 周期\n{}\n\n## 口径\n{}\n\n不编会计分录。{}\n",
        header("资金计划草稿"),
        nonempty(&s(args, "period"), "待填"),
        nonempty(&s(args, "notes"), "待填"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：CPF 缴交义务只写 CPF Board 标题。"),
            cn_only(&jur, "CN：工资专户 / 农民工工资条例只写标题。"),
        ),
    );
    match ctx.write_md("资金计划草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn tax_calendar(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let rows = if jur == "DUAL" {
        "| GST（SG 栏） | 申报期空栏 | 页述现行 9%；税额待填 |\n| CPF（SG 栏） | 待核雇主义务 |  |\n| 增值税（另一辖区栏） | 待按主管机关核对 | 仅当另一辖区为 CN 时用此行 |"
    } else if jur == "SG" {
        "| GST | 申报期空栏（IRAS F5 当期待填） | 页述现行 9%；税额待填；不是筹划意见 |\n| 企业所得税 | 申报期空栏 | 税额待填 |\n| CPF | 待核雇主义务 |  |"
    } else {
        "| 增值税 | 待按主管机关核对 | 不是筹划意见 |\n| 附加税费 | 待核 |  |\n| 企业所得税 | 待核 |  |"
    };
    let md = format!(
        "{}{banner}\n| 税种 | 申报节点 | 备注 |\n| --- | --- | --- |\n{rows}\n\n[A001] 税率与节点以主管机关原文为准，禁止编造条款号。{}{}\n",
        header("税务日历/检查表"),
        sg_only(&jur, "SG 施工服务征 GST 以 IRAS Construction 页为准；Current GST rates 页述现行标准税率 9%。境外土地零税率不代判。禁止把 7%/8% 写成现行税率。"),
        if jur == "DUAL" {
            "DUAL 分栏，不得把另一辖区税种写进 SG 栏。"
        } else {
            ""
        },
    );
    match ctx.write_md("税务检查表.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn supervision_reply(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let notice = nonempty(&s(args, "notice"), "待填");
    let points = nonempty(&s(args, "reply_points"), "待填");
    let blob = format!("{notice}\n{points}");
    let stop_note = if blob.contains("暂停") || blob.contains("复工") || blob.contains("停工") {
        "暂停令、复工报审只出目录和拟办提纲。本岗不签发复工。"
    } else {
        "若来文是暂停/复工，只出目录和拟办提纲。本岗不签发复工。"
    };
    let md = format!(
        "{}{banner}\n本回复是资料草稿，不是监理指令。待持证人员审核签发后报出。\n\n## 1 文头\n工程名称待填。回复编号待填。对应来文编号/日期待填。[A001]\n\n## 2 致\n致：项目监理机构。抄送栏待填。\n\n## 3 来文要点复述\n{notice}\n\n只复述用户提供的事由、部位、条数，不扩写没给的事实。\n\n## 4 原因分析\n管理/工艺/材料/资料。缺事实则待填。[A001]\n\n## 5 拟办\n{points}\n\n逐条对应来文，一条不漏。举一反三和预防只作栏目，不编造已培训记录。\n\n{stop_note}\n\n## 6 完成时限\n从来文或合同抄，否则 [A001] 待填。\n\n## 7 证据目录\n| 证据 | 本稿 |\n| --- | --- |\n| 整改前后影像 | 待附 |\n| 检查记录 | 待附 |\n| 检测报告 | 待附 |\n| 方案/交底目录 | 待附 |\n\n## 8 自检\n项目技术/质量负责人栏空白。\n\n## 9 签发\n本回复为 AI 草稿，待项目经理等持证人员审核签发后报出。\n\n## 10 闭合台账行\n| 来文号 | 要求闭合日 | 实际回复日 | 复查意见 |\n| --- | --- | --- | --- |\n| 待填 | 待填 | 待填 | （空，复查属监理） |\n\n## 11 禁令\n不写验收合格、资料已闭合可备案。不冒充总监签发。不编报告编号、强度、闭合天数。暂停/复工只出目录。\n\n{}\n",
        header("监理通知回复草稿"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：BCA construction site records / record structural plan C-forms 只写标题。"),
            cn_only(&jur, "CN：建设工程监理规范只写全名。"),
        ),
    );
    match ctx.write_md("监理回复草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn job_brief(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 岗位\n{}\n\n## 职责\n{}\n\n薪资带宽：用户未给则不编。{}\n",
        header("招聘简报"),
        nonempty(&s(args, "role"), "待填"),
        nonempty(&s(args, "duties"), "待填"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：Fair Consideration Framework / Key Employment Terms 只写标题。"),
            cn_only(&jur, "CN：劳动合同法招用告知口径只写标题，不编薪资。"),
        ),
    );
    match ctx.write_md("招聘简报.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn labor_checklist(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let extra = if jur == "SG" || jur == "DUAL" {
        format!("{banner}- 可点名 Employment Act / Key Employment Terms / Fair Consideration Framework，条款 UNSPECIFIED。\n- Work Permit 薪资发放只列 MOM 页标题，不代判欠薪。")
    } else {
        format!("{banner}- 可点名《劳动合同法》/《劳动法》/《保障农民工工资支付条例》，条款 UNSPECIFIED。")
    };
    let md = format!(
        "{}合同类型：{}\n\n{extra}\n\n| 检查项 | 结果 |\n| --- | --- |\n| 主体资格 | 待核 |\n| 工作内容与地点 | 待核 |\n| 工时与休息 | 待核 |\n| 报酬与支付 | 待核 |\n| 社会保险/意外 | 待核 |\n\n[A001] 普法口径，不构成诉讼意见。\n",
        header("劳动合同检查表"),
        nonempty(&s(args, "contract_type"), "待填"),
    );
    match ctx.write_md("劳动合同检查表.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn admin_doc(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 文种\n{}\n\n## 事由\n{}\n\n## 正文\n{}\n\n用印审批栏留空。{}\n",
        header("公文草稿"),
        nonempty(&s(args, "doc_type"), "请示"),
        nonempty(&s(args, "subject"), "待填"),
        nonempty(&s(args, "body"), "待填"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：ACRA / Bizfile 只写门户，不编注册号。"),
            cn_only(&jur, "CN：党政机关公文格式只写全名，用印栏留空。"),
        ),
    );
    match ctx.write_md("公文草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn ops_outline(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 系统\n{}\n\n## 账号与权限\n待按最小权限列。禁止在知识库写密钥。\n\n## 故障升级\nL1 现场 → L2 项目 IT → L3 厂商，联系人待填。\n\n{}\n",
        header("运维手册提纲"),
        nonempty(&s(args, "system"), "待填"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：PDPA / CSA Codes of Practice 只写标题。"),
            cn_only(&jur, "CN：网络安全法 / 个保法只写全名。"),
        ),
    );
    match ctx.write_md("运维手册提纲.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn backup_policy(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 系统\n{}\n\n## 策略\n- RPO/RTO：待填\n- 介质与异地：待填\n- 恢复演练：待排\n\n[A001] 不编小时数。{}\n",
        header("备份策略草稿"),
        nonempty(&s(args, "systems"), "待填"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：PDPA Care of Personal Data 只写原则名。"),
            cn_only(&jur, "CN：个保法只写全名，不编 RPO 小时。"),
        ),
    );
    match ctx.write_md("备份策略草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn worker_brief(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n今天干什么：{}\n\n盯什么：{}\n\n口头三分钟。不要讲已经能作业。数字没有就说还没量，别猜。{}\n",
        header("班前白话稿"),
        nonempty(&s(args, "work_today"), "待填"),
        nonempty(&s(args, "watchouts"), "临边、洞口、吊装、用电"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：toolbox meeting 导则只写标题。"),
            cn_only(&jur, "CN：班前会不是安全技术交底。"),
        ),
    );
    match ctx.write_md("班前白话稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn pm_daily(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 形象进度\n{}\n\n## 人机料\n{}\n\n## 安全质量记事\n{}\n\n{}本日报不是监理日志。\n",
        header("项目日报草稿"),
        nonempty(&s(args, "progress"), "待填"),
        nonempty(&s(args, "resources"), "待填"),
        nonempty(&s(args, "hse"), "待填"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：BCA construction site records 只写标题。"),
            cn_only(&jur, "CN：施工日志只写习惯名，不是监理日志。"),
        ),
    );
    match ctx.write_md("项目日报草稿.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn score_weight_table(facts: &crate::extract::TenderFacts) -> String {
    if facts.score_rows.is_empty() {
        return "- 未在原文检出评标权重表 [A001]".into();
    }
    let mut md = String::from("| 项 | 原文权重 | 来源句 |\n| --- | --- | --- |\n");
    for r in &facts.score_rows {
        md.push_str(&format!("| {} | {} | {} |\n", r.label, r.weight, r.source));
    }
    md
}

fn workhead_table(facts: &crate::extract::TenderFacts) -> String {
    if facts.workheads.is_empty() {
        return "- 未在原文检出 workhead [A001]".into();
    }
    let mut md = String::from("| 原文 workhead | 本项目是否点名 |\n| --- | --- |\n");
    for w in &facts.workheads {
        md.push_str(&format!("| {w} | 原文已点名 |\n"));
    }
    md
}

fn envelope_block(facts: &crate::extract::TenderFacts) -> String {
    if facts.envelope.is_empty() {
        return "- 未在原文点名 Two Envelope / 双信封 [A001]".into();
    }
    let mut md = String::from("点名：是\n");
    for e in &facts.envelope {
        md.push_str(&format!("- {e}\n"));
    }
    md
}

fn bullets_or(items: &[String], empty: &str) -> String {
    if items.is_empty() {
        format!("- {empty}")
    } else {
        items.iter().map(|i| format!("- {i}")).collect::<Vec<_>>().join("\n")
    }
}

fn nonempty(s: &str, fallback: &str) -> String {
    if s.trim().is_empty() {
        fallback.to_string()
    } else {
        s.to_string()
    }
}

fn sg_only(jur: &str, note: &str) -> String {
    if jur == "SG" || jur == "DUAL" {
        note.to_string()
    } else {
        String::new()
    }
}

fn cn_only(jur: &str, note: &str) -> String {
    if jur == "CN" || jur == "DUAL" {
        note.to_string()
    } else {
        String::new()
    }
}

fn zone_banner(args: &Value) -> (String, String) {
    let jur = normalize_jurisdiction(&s(args, "jurisdiction"));
    let other = s(args, "other_jurisdiction");
    let banner = if jur == "DUAL" {
        let other = nonempty(&other, "UNSPECIFIED");
        format!(
            "- 辖区：DUAL（SG + {other}）\n- DUAL 必须分栏点名两套门户，不得只套一套规范族。另一辖区未给则 [A001]。\n"
        )
    } else {
        format!("- 辖区：{jur}\n")
    };
    (jur, banner)
}

fn expert_outline(
    ctx: &mut ToolCtx,
    filename: &str,
    title: &str,
    args: &Value,
    fields: &[(&str, &str)],
    rules: &str,
) -> String {
    let (jur, banner) = zone_banner(args);
    let mut md = format!("{}{banner}\n", header(title));
    for (key, label) in fields {
        md.push_str(&format!("## {label}\n{}\n\n", nonempty(&s(args, key), "待填")));
    }
    let rules_out = if jur == "CN" {
        rules
            .lines()
            .filter(|l| !l.contains("SG：") && !l.contains("SG:"))
            .collect::<Vec<_>>()
            .join("\n")
    } else if jur == "SG" {
        rules
            .lines()
            .filter(|l| !l.contains("CN：") && !l.contains("CN:"))
            .collect::<Vec<_>>()
            .join("\n")
    } else {
        rules.to_string()
    };
    md.push_str(&format!(
        "## 口径\n{rules_out}\n\n[A001] 未提供的参数一律待填。规范只写全名，条款 UNSPECIFIED。本文件不是签认件。\n"
    ));
    if jur == "SG" || jur == "DUAL" {
        md.push_str(
            "\n## 编制依据（只列标题）\n- Workplace Safety and Health Act；Building Control Act / Approved Document；SCDF Fire Code 2023；PUB Codes of Practice：条款 UNSPECIFIED。\n- 禁止把中国大陆危大或施工规范族当作新加坡依据。\n",
        );
    }
    if jur == "DUAL" {
        md.push_str("\n## 另一辖区栏\n只列用户点名的另一辖区门户全名，条款 UNSPECIFIED。\n");
    }
    match ctx.write_md(filename, &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn plumbing_memo(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "给排水专业说明草稿.md",
        "给排水专业说明草稿",
        args,
        &[("scope", "范围"), ("open_items", "开放问题")],
        "- 无市政资料、标高、水压不编管径和泵型。\n- 消防水量不替代消防专篇。\n- SG：PUB Surface Water Drainage / Sewerage and Sanitary Works / SS 636 只写全名。\n- CN：给水排水设计标准只写全名。",
    )
}

fn hvac_memo(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "暖通专业说明草稿.md",
        "暖通专业说明草稿",
        args,
        &[("scope", "范围"), ("open_items", "开放问题")],
        "- 无负荷计算不定冷机、多联机、风管断面。\n- 不编排烟量、新风量保证值。\n- SG：Fire Code 章名 Mechanical Ventilation & Smoke Control 只列章名；SS 553:2026 / SS 554 只写全名。\n- CN：民用建筑供暖通风与空气调节设计规范只写全名。",
    )
}

fn electrical_memo(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "电气专业说明草稿.md",
        "电气专业说明草稿",
        args,
        &[("scope", "范围"), ("open_items", "开放问题")],
        "- 无负荷不选变压器容量。\n- 弱电品牌与点数交智能化弱电岗。\n- SG：Fire Code 章名 Electrical Power Supplies / Emergency Lighting 只列章名；电气装置规程族名 SS 638 / SS 650。\n- CN：民用建筑电气设计标准只写全名。",
    )
}

fn fire_protect_brief(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "消防专篇提纲.md",
        "消防专篇提纲",
        args,
        &[("scope", "范围"), ("systems", "系统")],
        "- 不编分区面积、疏散距离、喷淋强度、耐火极限。\n- 不宣称通过消防审图。\n- SG：SCDF Fire Code 2023 与 Fire Safety Act 只列标题。\n- CN：建筑设计防火规范只写全名。\n- 禁止写开工许可或审图结论。",
    )
}

fn steel_memo(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "钢结构专业说明草稿.md",
        "钢结构专业说明草稿",
        args,
        &[("system", "体系"), ("open_items", "开放问题")],
        "- 无跨度/荷载不写梁高、螺栓、焊缝。\n- 不编防火涂料厚度。\n- SG：可接受解写 SS EN 1993 / SS EN 1994 全名，条款 UNSPECIFIED。\n- CN：钢结构设计标准只写全名。",
    )
}

fn landscape_memo(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "景观专业说明草稿.md",
        "景观专业说明草稿",
        args,
        &[("scope", "范围"), ("open_items", "开放问题")],
        "- 无苗木表不编胸径、冠幅。\n- SG：NParks Guidelines on Greenery Provision and Tree Conservation Version 5.1 只写全名。\n- CN：城市绿地设计规范只写全名。\n- 不宣称通过绿化验收。",
    )
}

fn interior_schedule(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "室内界面表.md",
        "室内界面表",
        args,
        &[("rooms", "房间"), ("finishes", "饰面")],
        "- 无样板/合同不编品牌和型号。\n- 装修消防会签消防岗。\n- 禁止写已满足消防规范。\n- SG：Code on Accessibility in the Built Environment 2025 / CONQUAS Internal Finishes 只写标题。\n- CN：建筑内部装修设计防火规范只写全名。",
    )
}

fn facade_brief(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "幕墙专篇提纲.md",
        "幕墙专篇提纲",
        args,
        &[("system", "体系"), ("open_items", "开放问题")],
        "- 无风压、层高、分格不写面板厚度和龙骨规格。\n- 不替代主体结构计算。\n- 不宣称通过幕墙专项论证。\n- SG：Code on Envelope Thermal Performance / Fire Code External Wall 只写标题。\n- CN：玻璃幕墙工程技术标准只写全名。",
    )
}

fn intel_weak_memo(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "弱电专业说明草稿.md",
        "弱电专业说明草稿",
        args,
        &[("systems", "系统"), ("open_items", "开放问题")],
        "- 不编点数、品牌、接口地址。\n- 电源与接地交电气岗。\n- 人脸/行踪字段会签 PDPA / 个保法，本岗不做法务结论。\n- SG：IMDA COPIF / CSA Codes of Practice 只写标题；COPIF 2026 咨询稿不是已生效 COP。\n- CN：个人信息保护法只写全名。",
    )
}

fn civil_defense_brief(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "人防专篇提纲.md",
        "人防/掩蔽所专篇提纲",
        args,
        &[("scope", "范围"), ("open_items", "开放问题")],
        "- 不编防护等级、门樘尺寸、墙厚。\n- SG：Household / Storey Shelter 走 Civil Defence Shelter Act + BCA TRHS / THSS 标题。\n- CN：人民防空地下室设计规范只写全名。\n- 禁止把 CN 人防地下室规范套到 SG。",
    )
}

fn hydraulic_outline(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "水利提纲.md",
        "水利提纲",
        args,
        &[("scope", "范围"), ("open_items", "开放问题")],
        "- 无水文地质不写设计洪水位和边坡系数。\n- 码头结构交港航岗。\n- SG：PUB Surface Water Drainage / Coastal Protection 只写标题。\n- CN：堤防/水闸/灌排设计规范只写全名。",
    )
}

fn port_outline(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "港航提纲.md",
        "港航提纲",
        args,
        &[("scope", "范围"), ("open_items", "开放问题")],
        "- 无水位、波浪、地质不写桩长和胸墙。\n- 堤身交水利岗。\n- SG：MPA 门户 + PUB Coastal Protection 只写标题。禁止把 JTS 当 MPA 条文。\n- CN：码头结构设计规范只写全名。",
    )
}

fn municipal_memo(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "市政道路原则.md",
        "市政道路原则",
        args,
        &[("scope", "范围"), ("open_items", "开放问题")],
        "- 无红线、交通量不写车道数保证值。\n- SG：LTA Street Works / Civil Design Criteria Rev A3 / SDRE Rev I / 道路结构保护区只写标题。\n- CN：城市道路工程设计规范只写全名。",
    )
}

fn bridge_outline(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "桥梁提纲.md",
        "桥梁提纲",
        args,
        &[("span_note", "跨径/已知"), ("open_items", "开放问题")],
        "- 无跨径、地质、水文不写梁高、钢束、桩长。\n- 河道开口会签水利。\n- SG：LTA Civil Design Criteria Rev A3 / 结构保护只写标题。禁止把 JTG 当 LTA 依据。\n- CN：公路桥涵设计通用规范只写全名。",
    )
}

fn tunnel_outline(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "隧道提纲.md",
        "隧道提纲",
        args,
        &[("method", "工法"), ("open_items", "开放问题")],
        "- 无地质纵断面不定支护参数。\n- 不替代危大论证和监测方案。\n- SG：LTA 铁路保护区 + MOM WSH + SCDF CPFPRT 2025 / CPFPRTS 2022 只写标题。\n- CN：公路隧道设计规范只写全名。",
    )
}

fn traffic_skeleton(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "交通报告骨架.md",
        "交通影响评价骨架",
        args,
        &[("corridor", "走廊/路口"), ("open_items", "开放问题")],
        "- 无交通调查不编流量和饱和度。\n- SG：LTA TIA Guidelines / Traffic Control at Work Zone Apr 2026 / Works on Public Streets 只写门户标题。\n- CN：道路交通安全法 / 城市道路交通标志和标线设置规范只写全名。",
    )
}

fn design_coord_minutes(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "设计会审纪要.md",
        "设计会审纪要",
        args,
        &[("issues", "问题"), ("attendees", "与会")],
        "- 每条须有责任专业与关闭条件。\n- 本纪要不改图，不是审图通过。\n- SG：CORENET X / APPBCA-2026-12 只写标题，本纪要不是网关已过。\n- CN：施工图设计文件审查管理办法只写全名。",
    )
}

fn bim_deliver_lod(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "BIM交付清单.md",
        "BIM 交付清单",
        args,
        &[("stage", "阶段"), ("lod", "细度/格式")],
        "- SG：CORENET X + IFC+SG；COP Level of Details 不是 AIA LOD 强制档。APPBCA-2026-12：2026-10-01 仅 GFA≥5,000 m² 强制 Gateway。\n- CN：建筑信息模型设计交付标准只写全名。\n- 不宣称具备局方报审资格或竣工移交条件。\n- 无业主 EIR 则矩阵待填。",
    )
}

fn resource_skip(t: &str) -> bool {
    matches!(
        t,
        "草稿提纲"
            | "资源负荷"
            | "资源计划"
            | "资源负荷表"
            | "峰值"
            | "待填"
            | "四周"
            | "master"
            | "lookahead"
    ) || (t.starts_with('W') && t.chars().skip(1).all(|c| c.is_ascii_digit()))
}

fn resource_kind(t: &str) -> &'static str {
    let low = t.to_lowercase();
    const PLANT: &[&str] = &[
        "塔吊", "泵车", "挖机", "吊车", "机械", "机具", "台班", "crane", "excavator", "pump", "tower",
    ];
    const MAT: &[&str] = &[
        "周转", "水泥", "砂", "材料", "rebar", "concrete", "钢筋", "模板", "混凝土",
    ];
    if PLANT.iter().any(|k| t.contains(k) || low.contains(k)) {
        return "plant";
    }
    if t.contains('工') || t.contains("班组") || t.contains("劳动力") {
        return "labor";
    }
    if MAT.iter().any(|k| t.contains(k) || low.contains(k)) {
        return "mat";
    }
    if low.contains("formwork") {
        return "labor";
    }
    "labor"
}

fn split_resource_qty(line: &str) -> (String, String, String) {
    const UNITS: &[&str] = &["工日", "台班", "m³", "m3", "吨", "kg", "人", "台"];
    for u in UNITS {
        if let Some(pos) = line.find(u) {
            let before = line[..pos].trim_end();
            let mut digits = String::new();
            for c in before.chars().rev() {
                if c.is_ascii_digit() || c == '.' {
                    digits.push(c);
                } else if c == ' ' && digits.is_empty() {
                    continue;
                } else {
                    break;
                }
            }
            if digits.is_empty() {
                continue;
            }
            let qty: String = digits.chars().rev().collect();
            let cut = before.trim_end_matches(|c: char| c.is_ascii_digit() || c == '.' || c == ' ');
            let name = format!("{}{}", cut, &line[pos + u.len()..])
                .split_whitespace()
                .collect::<Vec<_>>()
                .join(" ");
            if name.is_empty() {
                continue;
            }
            return (name, format!("{qty}{u}"), "用户给定".into());
        }
    }
    (line.trim().to_string(), "TBD".into(), "待填".into())
}

fn parse_resource_items(blob: &str) -> (Vec<(String, String, String)>, Vec<(String, String, String)>, Vec<(String, String, String)>) {
    let mut labor = Vec::new();
    let mut plant = Vec::new();
    let mut mat = Vec::new();
    for raw in blob.replace('；', "\n").replace(';', "\n").lines() {
        let mut t = raw.trim().to_string();
        if let Some(rest) = t.strip_prefix("写一份") {
            t = rest.trim().to_string();
        }
        if t.is_empty() || resource_skip(&t) {
            continue;
        }
        if t.starts_with('#') || t.starts_with("内部") {
            continue;
        }
        if t.chars().count() > 80 {
            t = t.chars().take(80).collect();
        }
        let (name, qty, src) = split_resource_qty(&t);
        if name.is_empty() || resource_skip(&name) {
            continue;
        }
        let row = (name, qty, src);
        match resource_kind(&t) {
            "plant" => plant.push(row),
            "mat" => mat.push(row),
            _ => labor.push(row),
        }
    }
    (labor, plant, mat)
}

fn resource_table(kind: &str, rows: &[(String, String, String)]) -> String {
    match kind {
        "labor" => {
            let mut out = String::from("| 工种 | 工作 | 计划时段 | 需用人数 | 来源 | 峰值周 | 可否错峰 |\n| --- | --- | --- | --- | --- | --- | --- |\n");
            if rows.is_empty() {
                out.push_str("| [A001] | 待填 | 待填 | TBD | 待填 | 待填 | 待填 |\n");
            } else {
                for (n, q, s) in rows {
                    out.push_str(&format!("| {n} | 待填 | 待填 | {q} | {s} | 待填 | 待填 |\n"));
                }
            }
            out
        }
        "plant" => {
            let mut out = String::from("| 机械名称 | 规格 | 进场日 | 退场日 | 台班或台数 | 对应工作 | 证件 |\n| --- | --- | --- | --- | --- | --- | --- |\n");
            if rows.is_empty() {
                out.push_str("| [A001] | 待填 | 待填 | 待填 | TBD | 待填 | 待核 |\n");
            } else {
                for (n, q, _) in rows {
                    out.push_str(&format!("| {n} | 待填 | 待填 | 待填 | {q} | 待填 | 待核 |\n"));
                }
            }
            out
        }
        _ => {
            let mut out = String::from("| 名称 | 需用窗口 | 计划进场 | 计划耗尽 | 堆场 | 甲指或自采 | 数量 |\n| --- | --- | --- | --- | --- | --- | --- |\n");
            if rows.is_empty() {
                out.push_str("| [A001] | 待填 | 待填 | 待填 | 待填 | 待填 | TBD |\n");
            } else {
                for (n, q, _) in rows {
                    out.push_str(&format!("| {n} | 待填 | 待填 | 待填 | 待填 | 待填 | {q} |\n"));
                }
            }
            out
        }
    }
}

fn plan_resource_peak(ctx: &mut ToolCtx, args: &Value) -> String {
    let (jur, banner) = zone_banner(args);
    let window = nonempty(&s(args, "window"), "待填");
    let blob = format!(
        "{}\n{window}\n{}\n{}\n{}\n{}\n{}",
        s(args, "trades"),
        s(args, "equipment"),
        s(args, "items"),
        s(args, "material"),
        s(args, "materials"),
        s(args, "package"),
    );
    let (labor, plant, mat) = parse_resource_items(&blob);
    let labor_tbl = resource_table("labor", &labor);
    let plant_tbl = resource_table("plant", &plant);
    let mat_tbl = resource_table("mat", &mat);
    let md = format!(
        "{}{banner}\n默认交付是表头和口径说明，不是劳动力需用计划定案，也不是采购订单。本表不报价。窗口：{window}。\n\n## 1 封面与声明\n对应总控版本、计划期、资源种类范围待填。[A001] 无定额、无劳务计划、无设备台账、无材料需用表时，数量列全部待填。\n\n## 2 输入清单\n须核对：总控或四周窗口、分部分项工程量来源、定额或企业消耗指标、劳务班组编制、机械台账与证件、甲指/自采划分、堆场与宿舍上限。缺哪一项，对应资源列不填数。\n\n## 3 劳动力负荷表头\n{labor_tbl}\n只汇总用户已给的人数。来源为定额工日或用户给定；否则待填。禁止按经验编人数。\n\n## 4 施工机具负荷表头\n{plant_tbl}\n特种设备证件待核。无证件不得列入进场安排。数量来自施工部署或用户台账，不来自本岗估算。\n\n## 5 主要材料与周转料表头\n{mat_tbl}\n数量来自需用计划或清单。本岗不算量、不组价。到货价改召唤采购；收发存改召唤仓管或现场材料。\n\n## 6 峰值与错峰\n横轴为周或旬，纵轴为数量（有数才画）。峰值时段待填。错峰口径：总工期不变，利用非关键工作时差削峰填谷。禁止为削峰压缩关键工作持续时间。\n\n## 7 冲突提示栏\n| 项 | 提示 |\n| --- | --- |\n| 宿舍/食堂容量 | 可能冲突，待用户给上限 |\n| 塔吊台班窗口 | 可能冲突，待用户给上限 |\n| 混凝土日供应 | 可能冲突，待用户给上限 |\n| 作业面人数密度 | 可能冲突，待用户给上限 |\n| 夜间施工许可 | 可能冲突，待用户给上限 |\n\n只标可能冲突。不写已经超标或已经合规。\n\n## 8 与周月、采购、资金的接口\n四周滚动看本表「这周人机料是否同时具备」；采购看需用窗口和提前期栏；资金看大额进场时点栏，金额待填，改召唤资金或验工计价。\n\n## 9 优化记录\n未做均衡，仅列表头。未计算时差，不写移动了哪些非关键工作。\n\n## 10 禁令\n不编工日、台班、吨数、综合单价、市场价。禁止宣称资源已经够用。无证件设备不列入进场安排。关键线路资源缺口必须回写总控，不得只在本表删掉该工作。\n\n{}\n",
        header("资源峰值表头"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：Code of Practice on Buildability 只写标题，最低分 UNSPECIFIED。C-Score 不是劳动力需用计划。"),
            cn_only(&jur, "CN：施工组织设计规范 / 劳动定额只写全名，不编工日。"),
        ),
    );
    match ctx.write_md("资源峰值表头.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn proc_vendor_eval(ctx: &mut ToolCtx, args: &Value) -> String {
    let vendor = nonempty(&s(args, "vendor"), "待填供方");
    let criteria = nonempty(&s(args, "criteria"), "资质 / 业绩 / 交期（待核）");
    let (jur, banner) = zone_banner(args);
    let md = format!(
        "{}{banner}\n## 供方\n{vendor}\n\n## 评价项\n{criteria}\n\n| 项 | 结果 |\n| --- | --- |\n| 主体资格 | 待核 |\n| 业绩 | 待核 |\n| 交期 | 待核 |\n| 报价 | 无报价不编价 |\n\n[A001] 不编分数和中标结论。本表不是定标决议。{}\n",
        header("供方评价表头"),
        sg_only(&jur, "SG：GeBIZ / BCA CRS 只写门户标题。"),
    );
    match ctx.write_md("供方评价表头.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn material_site_recon(ctx: &mut ToolCtx, args: &Value) -> String {
    let items = split_lines(&s(args, "items"));
    let notes = nonempty(&s(args, "notes"), "待填");
    let (jur, banner) = zone_banner(args);
    let mut md = format!(
        "{}{banner}\n| 材料 | 应耗 | 实耗 | 节超 | 备注 |\n| --- | --- | --- | --- | --- |\n",
        header("材料耗用核算表头")
    );
    if items.is_empty() {
        md.push_str("| 待填 | TBD | TBD | TBD | 无盘点不编 |\n");
    }
    for it in items {
        md.push_str(&format!("| {it} | TBD | TBD | TBD | {notes} |\n"));
    }
    md.push_str("\n[A001] 无盘点不编盈亏。无指标不编应耗百分比。禁止编造损耗率。");
    md.push_str(&sg_only(&jur, "SG：Factory Notification 不是损耗公式。"));
    md.push('\n');
    match ctx.write_md("材料耗用核算表头.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn lab_record_ledger(ctx: &mut ToolCtx, args: &Value) -> String {
    let samples = split_lines(&s(args, "samples"));
    let (jur, banner) = zone_banner(args);
    let table = if samples.is_empty() {
        "| 试样 | 试验项 | 报告编号 | 仪器检定 | 结论 |\n| --- | --- | --- | --- | --- |\n| 待填 | 待填 | 待核 | 待核 | 待填 |".to_string()
    } else {
        let mut out = String::from("| 试样 | 试验项 | 报告编号 | 仪器检定 | 结论 |\n| --- | --- | --- | --- | --- |\n");
        for s0 in &samples {
            out.push_str(&format!("| {s0} | 待填 | 待核 | 待核 | 待填 |\n"));
        }
        out
    };
    let basis = if jur == "SG" {
        "公开名称只写族名。试验方法标准只写名称，正文禁止摘步骤。条款 unspecified_clause。".to_string()
    } else {
        "《建设工程质量检测管理办法》；《中华人民共和国计量法》。试验方法标准只写名称，正文禁止摘步骤。".to_string()
    };
    let md = format!(
        "{}{banner}\n内部讨论用，不是 CMA/CNAS 证书，不是竣工归档正本。不填检测数据，不给合格结论。\n\n## 1 封面\n工程或试验室名称、年度、台账种类待填。[A001]\n\n## 2 编号总则\n检测合同、委托单、原始记录、检测报告按年度统一编号，编号连续，不得随意抽撤、涂改。用户未给现行编号规则则只出表头 + [A001] 待填，不发明一套工程代号。\n\n## 3 建议分册\n- 原材料进场复试台账\n- 混凝土 / 砂浆试配与施工配合比通知台账（只登记编号与日期，用量见 lab-mix）\n- 试件成型、养护、试压台账\n- 见证取样送检台账\n- 检测结果不合格项目台账（单独建册）\n- 仪器设备台账与检定/校准/期间核查计划\n- 标准物质与试模、养护室温湿度记录\n\n{table}\n\n## 4 原始记录纪律\n记录真实、按年连续编号。严禁涂改，笔误杠改并签改人改期。\n\n## 5 仪器三件事\n检定：对照法定要求给出合格与否，属法制计量。未检、逾期、不合格不得使用。校准：给出示值误差和不确定度，不等于法定检定。期间核查：两次检定或校准之间的运行检查。仪器超检定期不得使用。追溯清单待用户提供，不编报告号。\n\n## 6 公开名称备查\n{basis}\n\n## 7 闭合检查表头\n| 检查 | 状态 |\n| --- | --- |\n| 有取样计划是否有委托单 | 待核 |\n| 有委托单是否有报告 | 待核 |\n| 有不合格是否有 24 小时上报和处置 | 待核 |\n| 有仪器是否在有效期内 | 待核 |\n\n缺一项标缺口。本稿不下归档结论。\n\n## 8 接口\n配合比通知单编号给 lab-mix；见证委托单给 lab-sample；资料总目录给 supervision；账物隔离给 warehouse。\n\n## 9 禁令\n不编造已完成的检定证书号、报告号、温湿度曲线。不把校准证书改写成法定检定。\n\n{}\n",
        header("试验台账骨架"),
        format!(
            "{}{}",
            sg_only(&jur, "SG：SAC laboratory accreditation 只写标题。"),
            cn_only(&jur, "CN：建设工程质量检测管理办法只写全名。"),
        ),
    );
    match ctx.write_md("试验台账骨架.md", &md) {
        Ok(m) => m,
        Err(e) => e,
    }
}

fn finance_book_check(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "核算检查表.md",
        "核算检查表",
        args,
        &[("period", "周期")],
        "- 不编会计分录和税率。\n- SG：GST / 账套口径以 IRAS / ACRA 原文为准。\n- CN：增值税法 / 会计法只写全名。\n- 本表不是审计意见。",
    )
}

fn hr_train_plan(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "培训计划骨架.md",
        "培训计划骨架",
        args,
        &[("audience", "对象"), ("topics", "课题")],
        "- 不宣布已培训可上岗。\n- SG：CSOC / BCSS / WSQ 只写课程全名，证书有效期待核。\n- CN：生产经营单位安全培训规定只写全名。\n- 签到不得预填代签。",
    )
}

fn admin_office_list(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "会务清单.md",
        "会务清单",
        args,
        &[("event", "事项")],
        "- 场地、议程、与会、资料目录只列表头。\n- 不代签发会议决定，不用印栏留空。\n- SG：PDPA / SFA 餐饮牌照只写标题，费用 UNSPECIFIED。\n- CN：党政机关公文格式只写全名。",
    )
}

fn it_app_srs(ctx: &mut ToolCtx, args: &Value) -> String {
    expert_outline(
        ctx,
        "需求说明书骨架.md",
        "需求说明书骨架",
        args,
        &[("system", "系统"), ("users", "用户")],
        "- 不编接口 URL、密钥、品牌锁定。\n- 人脸/行踪会签 PDPA / 个保法。\n- 不宣称已合规可上线。\n- SG：CSA Cybersecurity Code of Practice for CII 2026 只写标题；未指定 CII 不得套时限。\n- CN：个人信息保护法 / 网络安全法只写全名。",
    )
}

fn clip(s: &str, n: usize) -> String {
    let t: String = s.chars().take(n).collect();
    if s.chars().count() > n {
        format!("{t}…")
    } else {
        t
    }
}

fn run_python(args: &[&str]) -> Result<String, String> {
    for exe in ["python", "py"] {
        let mut cmd = Command::new(exe);
        if exe == "py" {
            cmd.arg("-3");
        }
        cmd.args(args);
        match cmd.output() {
            Ok(out) => {
                let stdout = String::from_utf8_lossy(&out.stdout);
                let stderr = String::from_utf8_lossy(&out.stderr);
                if out.status.success() {
                    return Ok(format!("{stdout}{stderr}"));
                }
                return Err(format!(
                    "python 退出 {}：{}",
                    out.status,
                    clip(&(stdout.to_string() + &stderr), 800)
                ));
            }
            Err(_) => continue,
        }
    }
    Err("本机找不到 python / py，无法填 docx 模板".into())
}
