let meta = #{
    name: "eval-parallel-16",
    description: "Max-out 16 parallel packing-agent evaluation lanes, then synthesize one gate report",
    phases: [
        #{ title: "Fanout", detail: "16 execute agents each run one regression script" },
        #{ title: "Synthesize", detail: "merge pass/fail into one scorecard summary" },
    ],
    when_to_use: "Full parallel gate suite (16 concurrent eval subagents)",
};

let lane_schema = #{
    "type": "object",
    "required": ["lane_id", "cmd", "exit_code", "pass", "summary"],
    "properties": #{
        "lane_id": #{ "type": "string" },
        "cmd": #{ "type": "string" },
        "exit_code": #{ "type": "integer" },
        "pass": #{ "type": "boolean" },
        "summary": #{ "type": "string" },
        "tail": #{ "type": "string" },
    },
};

let synth_schema = #{
    "type": "object",
    "required": ["n_lanes", "n_pass", "n_fail", "all_green", "failed_lanes", "headline"],
    "properties": #{
        "n_lanes": #{ "type": "integer" },
        "n_pass": #{ "type": "integer" },
        "n_fail": #{ "type": "integer" },
        "all_green": #{ "type": "boolean" },
        "failed_lanes": #{ "type": "array", "maxItems": 16, "items": #{ "type": "string" } },
        "headline": #{ "type": "string" },
        "report_md": #{ "type": "string" },
    },
};

// Exactly 16 lanes — saturates host concurrent child cap (16).
// Each lane: one shell command, report exit_code/pass/summary.
let lanes = [
    #{ id: "ns_golden", cmd: "python scripts/test_nonstandard_inspect.py" },
    #{ id: "ns_new", cmd: "python scripts/test_nonstandard_new_fixtures.py" },
    #{ id: "ns_pack", cmd: "python scripts/test_nonstandard_pack_smoke.py" },
    #{ id: "expand23", cmd: "python scripts/test_expand_pack_scope.py" },
    #{ id: "gtable15", cmd: "python scripts/run_generic_table_tests.py" },
    #{ id: "table_api", cmd: "python scripts/test_table_api_parse.py" },
    #{ id: "path_vgm", cmd: "python scripts/test_path_honesty_vgm.py" },
    #{ id: "profile", cmd: "python scripts/test_generic_profile_auto.py" },
    #{ id: "workteams", cmd: "python scripts/eval_workteams_cli.py --tiny-only" },
    #{ id: "mid50", cmd: "python scripts/test_mid50_cog.py" },
    #{ id: "mid50_uniform", cmd: "python scripts/test_mid50_uniform.py" },
    #{ id: "debate", cmd: "python scripts/test_bounded_debate.py" },
    #{ id: "dirty", cmd: "python scripts/test_data_clean_dirty_tables.py" },
    #{ id: "demo_ui", cmd: "python scripts/test_demo_simple_ui.py" },
    #{ id: "model_shadow", cmd: "python scripts/test_model_eval_shadow.py" },
    #{ id: "mapper_unit", cmd: "python scripts/test_table_mapper_unit.py" },
];

phase("Fanout");
log("Launching 16 parallel eval lanes (host max concurrent children = 16)");

let jobs = [];
let li = 0;
for lane in lanes {
    let lid = lane.id;
    let lcmd = lane.cmd;
    let p = "";
    p += "You are eval lane " + lid + " of 16. ";
    p += "Working directory is the packing-agent workspace root (git repo with scripts/). ";
    p += "Run EXACTLY this command with the shell/terminal tool and wait until it finishes: ";
    p += lcmd;
    p += " ";
    p += "Do not reimplement tests. Drive the real script. ";
    p += "Return JSON fields: lane_id=" + lid + ", cmd as given, exit_code from the process, ";
    p += "pass=true only if exit_code is 0, summary is one Chinese or English line of result, ";
    p += "tail is last ~20 lines of stdout/stderr (truncate if huge). ";
    p += "If the script file is missing, exit_code=127 pass=false with summary missing script.";
    jobs.push(#{
        prompt: p,
        label: "eval:" + lid,
        capability_mode: "execute",
        output_schema: lane_schema,
    });
    li += 1;
}

let results = parallel(jobs);

phase("Synthesize");
let n_ok = 0;
let n_bad = 0;
let failed = [];
let rows = "";
let i = 0;
for r in results {
    let lid = "lane_" + i.to_string();
    let ok = false;
    let sum = "no_result";
    let code = -1;
    if r != () && r.success && r.output != () {
        if r.output.lane_id != () { lid = r.output.lane_id; }
        if r.output.pass == true { ok = true; }
        if r.output.exit_code != () {
            // exit 0 is pass even if pass field wrong
            if r.output.exit_code == 0 { ok = true; }
            code = r.output.exit_code;
        }
        if r.output.summary != () { sum = r.output.summary; }
    } else {
        sum = "agent_failed_or_empty";
        ok = false;
    }
    if ok {
        n_ok += 1;
        rows += "| PASS | " + lid + " | " + code.to_string() + " | " + sum + " |\n";
    } else {
        n_bad += 1;
        failed.push(lid);
        rows += "| FAIL | " + lid + " | " + code.to_string() + " | " + sum + " |\n";
    }
    i += 1;
}

let all_green = n_bad == 0;
let headline = "eval-parallel-16: pass=" + n_ok.to_string() + " fail=" + n_bad.to_string();
if all_green {
    headline += " ALL_GREEN";
} else {
    headline += " HAS_FAIL";
}

let md = "";
md += "# eval-parallel-16 report\n\n";
md += headline + "\n\n";
md += "| status | lane | exit | summary |\n";
md += "|--------|------|------|--------|\n";
md += rows;
md += "\nHost concurrent children saturated at 16. Tools-first packing gates only.\n";

let sp = write_scratch_file("eval_parallel_16_report.md", md);
log(headline);

// Optional structured synth agent for narrative (uses 17th budget slot if remaining)
let b = budget();
let failed_json = json_encode(failed);
if b.remaining >= 1 {
    let sprompt = "";
    sprompt += "Synthesize packing-agent parallel eval. ";
    sprompt += "n_lanes=16 n_pass=" + n_ok.to_string() + " n_fail=" + n_bad.to_string() + " ";
    let ags = "false";
    if all_green { ags = "true"; }
    sprompt += "all_green=" + ags + " failed_lanes=" + failed_json + " ";
    sprompt += "Write short Chinese headline and report_md (markdown table summary). ";
    sprompt += "Do not invent passes — only use the numbers given. ";
    let syn = agent(sprompt, #{
        label: "synth-eval16",
        capability_mode: "read-only",
        output_schema: synth_schema,
    });
    if syn != () && syn.success && syn.output != () {
        if syn.output.report_md != () && syn.output.report_md != "" {
            write_scratch_file("eval_parallel_16_report.md", syn.output.report_md);
        }
        complete(#{
            path: sp,
            headline: headline,
            n_lanes: 16,
            n_pass: n_ok,
            n_fail: n_bad,
            all_green: all_green,
            failed_lanes: failed,
            synth: syn.output,
        });
    }
}

complete(#{
    path: sp,
    headline: headline,
    n_lanes: 16,
    n_pass: n_ok,
    n_fail: n_bad,
    all_green: all_green,
    failed_lanes: failed,
});
