"""What the term list does for voice input — measured, not asserted.

Four prompts, same model and decode call as /api/asr (asr.run_model_detail):
  A  no prompt
  B  generic Mandarin cue only
  C  generic cue + the domain sentence (asr.domain_prompt)
  D  generic cue + domain sentence + the term list (asr.build_prompt, what ships)
C -> D isolates the term list; B -> C isolates the domain sentence; B -> D is what shipping changes.
Two conditions: the clip as committed, and the same clip with seeded white noise at SNR_DB.

Metrics, per subset (lexicon / heldout), condition and prompt:
  term accuracy   key terms found in the transcript / key terms spoken (primary). Traditional
                  characters in the transcript are folded to simplified first, so a script change
                  is not counted as a recognition change
  CER             character edit distance / reference length (unfolded: script counts as an error)
  insertions      term-list words in the transcript beyond how often they were spoken, longest
                  words consumed first so 装箱单 is not also counted as 箱单
  traditional     transcripts containing traditional characters
  fallback        runs where Whisper fell back to sampling (temperature > 0); those transcripts
                  depend on the random seed, and flips they take part in are marked *
  flips           key terms that went miss->hit and hit->miss between two prompts

    python eval/asr/run_eval.py              # needs faster-whisper; writes results.json + README table
    python eval/asr/run_eval.py --limit 4    # smoke: prints a table, writes nothing
    python eval/asr/run_eval.py --check      # no model: validates the set, clips, config, and README numbers
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "demo"))

import asr  # noqa: E402  (stdlib-only at import time)

ARMS = {"A": "无提示", "B": "普通话提示", "C": "普通话 + 领域说明", "D": "普通话 + 领域说明 + 术语表（上线配置）"}
SUBSETS = {"lexicon": "词表内术语", "heldout": "词表外术语"}
FLIPS = (("C", "D", "只加术语表"), ("B", "D", "上线配置相对普通话提示"))
SNR_DB = 10.0
SEED = 20260918
RESULTS = HERE / "results.json"
REPORT = HERE / "README.md"
TABLE_START, TABLE_END = "<!-- asr-table:start -->", "<!-- asr-table:end -->"

# Traditional → simplified for every character the set scores or Whisper wrote here; generated
# once with OpenCC t2s and frozen so --check stays standard-library only.
_FOLD = str.maketrans(
    "與專個舉麼習於倉們價衆會體佔來側備關況準鳳擊剛別辦務單歷參臺嘆後聽員響場堅報牆處復寬對將層屬帶幫應龐廢開張強彈當慣戲戶執護擔擰據攪斬時曉術機條構櫃標樣樁檢樓榮匯沒漿澆測滲減遊滯現電監盡眾碼礎禮離種積籤簡簽級結給綁編總紅練終經綜縫羅聯聖勝膠腳艙獲衊襯襲裝裡製評認誰證譜計訂議設試話請談貧貨貴費負貪貼資軌輕輝這進連適選郵釋裏鋼銘銷鍵長閉間隊陣頂項須預領頻騰驗鳥雞",
    "与专个举么习于仓们价众会体占来侧备关况准凤击刚别办务单历参台叹后听员响场坚报墙处复宽对将层属带帮应庞废开张强弹当惯戏户执护担拧据搅斩时晓术机条构柜标样桩检楼荣汇没浆浇测渗减游滞现电监尽众码础礼离种积签简签级结给绑编总红练终经综缝罗联圣胜胶脚舱获蔑衬袭装里制评认谁证谱计订议设试话请谈贫货贵费负贪贴资轨轻辉这进连适选邮释里钢铭销键长闭间队阵顶项须预领频腾验鸟鸡",
)
_TRADITIONAL = {chr(k) for k in _FOLD}


def conditions(snr_db: float) -> dict:
    return {"clean": "原始音频", "noise": f"加白噪声 SNR {snr_db:g} dB"}


# ---------------- set and clips ----------------

def load_items() -> list[dict]:
    return json.loads((HERE / "sentences.json").read_text(encoding="utf-8"))["items"]


def sha256(path: Path) -> str:
    """Raw bytes: for the binary clips."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(path: Path) -> str:
    """Text files hash the same with LF or CRLF, so a Windows checkout (autocrlf) does not fail --check."""
    return hashlib.sha256(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest()


def validate_set(items: list[dict], lexicon: list[str]) -> None:
    """The set's own promises: lexicon rows test listed terms, heldout rows contain no listed word."""
    for item in items:
        if item["subset"] == "lexicon":
            for alts in item["terms"]:
                assert any(a in lexicon for a in alts), (item["id"], alts)
                assert any(a in item["text"] for a in alts), (item["id"], alts)
        elif item["subset"] == "heldout":
            listed = [t for t in lexicon if t in item["text"]]
            assert not listed, (item["id"], listed)
            for alts in item["terms"]:
                assert not any(a in lexicon for a in alts), (item["id"], alts)
                assert any(a in item["text"] for a in alts), (item["id"], alts)
        else:
            raise AssertionError(item["id"])


def load_manifest(verify: bool = True) -> list[dict]:
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    if verify:
        for clip in manifest:
            path = HERE / "clips" / clip["clip"]
            assert path.is_file(), path
            assert sha256(path) == clip["sha256"], f"{clip['clip']} changed since make_clips.py"
    return manifest


# ---------------- normalisation and scoring ----------------

_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}
_CN_NUM = re.compile("[零〇一二两三四五六七八九十百千万]+")


def _cn_to_int(run: str) -> str:
    if not any(ch in _UNITS for ch in run):  # 二零二六 → 2026
        return "".join(str(_DIGITS[ch]) for ch in run)
    total = section = num = 0
    for ch in run:
        if ch in _DIGITS:
            num = _DIGITS[ch]
        elif ch == "万":
            total += (section + num) * 10000
            section = num = 0
        else:
            section += (num or 1) * _UNITS[ch]
            num = 0
    return str(total + section + num)


def normalise(text: str, fold: bool = False) -> str:
    """Same rule on both sides: NFKC, drop punctuation and spaces, lower-case, Chinese numerals → digits.
    fold=True also maps traditional characters to simplified (term scoring only)."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    if fold:
        text = text.translate(_FOLD)
    text = "".join(ch for ch in text if ch.isalnum())
    return _CN_NUM.sub(lambda m: _cn_to_int(m.group(0)), text)


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def term_hits(item: dict, hyp: str) -> list[bool]:
    h = normalise(hyp, fold=True)
    return [any(normalise(a) in h for a in alts) for alts in item["terms"]]


def _term_counts(text: str, lexicon: list[str]) -> dict:
    """How often each listed word occurs, longest first, each match consumed (装箱单 is not also 箱单)."""
    counts = {}
    for term in sorted({normalise(t) for t in lexicon}, key=len, reverse=True):
        n = text.count(term)
        if n:
            counts[term] = n
            text = text.replace(term, "\x00")
    return counts


def insertions(ref: str, hyp: str, lexicon: list[str]) -> list[str]:
    r = _term_counts(normalise(ref, fold=True), lexicon)
    h = _term_counts(normalise(hyp, fold=True), lexicon)
    return [t for t, n in h.items() for _ in range(max(0, n - r.get(t, 0)))]


def has_traditional(hyp: str) -> bool:
    return any(ch in _TRADITIONAL for ch in hyp)


# ---------------- summary (pure: results.json → numbers) ----------------

def summarise(results: dict, items: list[dict]) -> dict:
    by_id = {i["id"]: i for i in items}
    lexicon = results["meta"]["lexicon"]
    cells: dict = {}
    for run in results["runs"]:
        item = by_id[run["id"]]
        key = (item["subset"], run["condition"], run["arm"])
        cell = cells.setdefault(key, {"terms": 0, "hits": 0, "edits": 0, "chars": 0, "insertions": 0,
                                      "traditional": 0, "fallback": 0, "clips": 0, "elapsed": 0.0, "audio": 0.0})
        hits = term_hits(item, run["hyp"])
        cell["terms"] += len(hits)
        cell["hits"] += sum(hits)
        cell["edits"] += edit_distance(normalise(item["text"]), normalise(run["hyp"]))
        cell["chars"] += len(normalise(item["text"]))
        cell["insertions"] += len(insertions(item["text"], run["hyp"], lexicon))
        cell["traditional"] += has_traditional(run["hyp"])
        cell["fallback"] += run["temperature"] > 0
        cell["clips"] += 1
        cell["elapsed"] += run["elapsed"]
        cell["audio"] += run["audio_seconds"]

    runs = {(r["clip"], r["condition"], r["arm"]): r for r in results["runs"]}
    flips: dict = {}
    for before_arm, after_arm, label in FLIPS:
        for (clip, cond, arm), before in runs.items():
            if arm != before_arm:
                continue
            after = runs[(clip, cond, after_arm)]
            item = by_id[before["id"]]
            mark = "*" if before["temperature"] > 0 or after["temperature"] > 0 else ""
            f = flips.setdefault(f"{before_arm}->{after_arm}/{item['subset']}/{cond}",
                                 {"label": label, "fixed": [], "broken": []})
            for alts, b, a in zip(item["terms"], term_hits(item, before["hyp"]), term_hits(item, after["hyp"])):
                tag = f"{alts[0]}（{clip.removesuffix('.webm')}）{mark}"
                if not b and a:
                    f["fixed"].append(tag)
                if b and not a:
                    f["broken"].append(tag)

    rows = []
    for subset in SUBSETS:
        for cond in ("clean", "noise"):
            for arm in ARMS:
                if (subset, cond, arm) not in cells:
                    continue
                c = cells[(subset, cond, arm)]
                rows.append({
                    "subset": subset, "condition": cond, "arm": arm,
                    "term_acc": round(100 * c["hits"] / c["terms"], 1), "hits": c["hits"], "terms": c["terms"],
                    "cer": round(100 * c["edits"] / c["chars"], 1), "insertions": c["insertions"],
                    "traditional": c["traditional"], "fallback": c["fallback"], "clips": c["clips"],
                    "rtf": round(c["elapsed"] / c["audio"], 3),
                })
    return {"rows": rows, "flips": dict(sorted(flips.items()))}


def render(summary: dict, meta: dict) -> str:
    opts = meta["decode_options"]
    cond = conditions(meta["snr_db"])
    lines = [
        TABLE_START,
        f"模型 faster-whisper `{meta['model']}`（{meta['device'].upper()} {meta['compute_type']}，"
        f"beam {opts['beam_size']}，VAD {'开' if opts['vad_filter'] else '关'}，随机种子 {meta['seed']}）· "
        f"术语表 {len(meta['lexicon'])} 词、上线提示 {meta['prompt_tokens']} / {meta['prompt_token_limit']} token · "
        f"{meta['n_clips']} 段音频（{meta['n_sentences']} 句 × {len(meta['voices'])} 种合成声音）",
        "",
        "| 术语 | 音频 | 提示 | 术语识别率 | 字错率 CER | 误插入词表词 | 含繁体 | 采样回退 | 实时率 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in summary["rows"]:
        lines.append(
            f"| {SUBSETS[r['subset']]} | {cond[r['condition']]} | {r['arm']} {ARMS[r['arm']]} | "
            f"**{r['term_acc']}%**（{r['hits']}/{r['terms']}） | {r['cer']}% | {r['insertions']} | "
            f"{r['traditional']}/{r['clips']} | {r['fallback']}/{r['clips']} | {r['rtf']} |"
        )
    lines += ["", "逐术语变化（术语（句子_声音）；带 * 的是其中一次识别用了采样回退，结果依赖随机种子）：", ""]
    for key, f in summary["flips"].items():
        arms, subset, c = key.split("/")
        lines.append(f"- {arms}（{f['label']}）· {SUBSETS[subset]} · {cond[c]}：修好 {len(f['fixed'])}，改坏 {len(f['broken'])}"
                     + (f"。修好：{'、'.join(f['fixed'])}" if f["fixed"] else "")
                     + (f"。改坏：{'、'.join(f['broken'])}" if f["broken"] else ""))
    lines.append(TABLE_END)
    return "\n".join(lines)


def replace_table(text: str, table: str) -> str:
    a, b = text.index(TABLE_START), text.index(TABLE_END) + len(TABLE_END)
    return text[:a] + table + text[b:]


# ---------------- running the model ----------------

def add_noise(audio, clip_name: str, snr_db: float):
    import numpy as np

    seed = int(hashlib.sha256(clip_name.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    power = float(np.mean(audio ** 2)) or 1e-12
    noise = rng.normal(0.0, (power / 10 ** (snr_db / 10)) ** 0.5, size=audio.shape)
    return (audio + noise).astype("float32")


def prompt_tokens(model, prompt: str) -> int:
    return len(model.hf_tokenizer.encode(" " + prompt.strip(), add_special_tokens=False).ids)


def current_prompts(lexicon: list[str]) -> dict:
    return {"A": None, "B": asr.GENERIC_PROMPT, "C": asr.domain_prompt(), "D": asr.build_prompt(lexicon)}


def run(limit: int | None) -> dict:
    import ctranslate2
    import faster_whisper
    from faster_whisper import WhisperModel

    items = load_items()
    lexicon = asr.load_lexicon()
    validate_set(items, lexicon)
    full = load_manifest()
    manifest = full[:limit] if limit is not None else full
    ctranslate2.set_random_seed(SEED)  # once: temperature-fallback sampling is otherwise unseeded
    model = WhisperModel(asr.MODEL_NAME, device=asr.DEVICE, compute_type=asr.COMPUTE_TYPE)
    prompts = current_prompts(lexicon)
    n_tok = prompt_tokens(model, prompts["D"])
    assert n_tok <= asr.PROMPT_TOKEN_LIMIT, f"term list is {n_tok} tokens; Whisper would cut its head off"

    runs = []
    for k, clip in enumerate(manifest, 1):
        clean = asr.decode((HERE / "clips" / clip["clip"]).read_bytes())  # the endpoint's own decode path
        for cond, audio in (("clean", clean), ("noise", add_noise(clean, clip["clip"], SNR_DB))):
            for arm, prompt in prompts.items():
                t = time.perf_counter()
                out = asr.run_model_detail(model, audio, prompt)  # the endpoint's own decode call
                runs.append({"clip": clip["clip"], "clip_sha256": clip["sha256"], "id": clip["id"],
                             "voice": clip["voice"], "condition": cond, "arm": arm, "hyp": out["text"],
                             "temperature": out["temperature"], "avg_logprob": round(out["avg_logprob"], 3),
                             "elapsed": round(time.perf_counter() - t, 3),
                             "audio_seconds": round(len(audio) / asr.SAMPLE_RATE, 3)})
        print(f"[{k}/{len(manifest)}] {clip['clip']}: D={runs[-5]['hyp']}", flush=True)

    return {
        "meta": {
            "model": asr.MODEL_NAME, "device": asr.DEVICE, "compute_type": asr.COMPUTE_TYPE,
            "faster_whisper": faster_whisper.__version__, "ctranslate2": ctranslate2.__version__,
            "decode_options": asr.DECODE_OPTIONS, "snr_db": SNR_DB, "seed": SEED, "prompts": prompts,
            "lexicon": lexicon, "lexicon_sha256": text_sha256(asr.LEXICON_PATH),
            "sentences_sha256": text_sha256(HERE / "sentences.json"),
            "prompt_tokens": n_tok, "prompt_token_limit": asr.PROMPT_TOKEN_LIMIT,
            "n_sentences": len({c["id"] for c in manifest}), "n_clips": len(manifest),
            "voices": sorted({c["voice"] for c in manifest}),
            "cpu": platform.processor() or platform.machine(), "cpu_count": os.cpu_count(),
            "complete": len(manifest) == len(full),
        },
        "runs": runs,
    }


def check() -> None:
    """CI gate without the model: the results must describe exactly what ships, clip for clip."""
    items = load_items()
    lexicon = asr.load_lexicon()
    validate_set(items, lexicon)
    manifest = load_manifest()
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    meta = results["meta"]
    assert meta["complete"], "results.json came from a partial run"
    stale = []
    if meta["prompts"] != current_prompts(lexicon):
        stale.append("prompts (GENERIC_PROMPT, DOMAIN or the term list)")
    if meta["lexicon_sha256"] != text_sha256(asr.LEXICON_PATH):
        stale.append("demo/asr_lexicon.txt")
    if meta["sentences_sha256"] != text_sha256(HERE / "sentences.json"):
        stale.append("sentences.json")
    for key, now in (("model", asr.MODEL_NAME), ("device", asr.DEVICE), ("compute_type", asr.COMPUTE_TYPE),
                     ("decode_options", asr.DECODE_OPTIONS), ("snr_db", SNR_DB), ("seed", SEED)):
        if meta[key] != now:
            stale.append(f"{key} ({meta[key]!r} -> {now!r})")
    assert not stale, "changed since the eval ran, rerun eval/asr/run_eval.py: " + "; ".join(stale)
    assert meta["prompt_tokens"] <= asr.PROMPT_TOKEN_LIMIT
    sha = {c["clip"]: c["sha256"] for c in manifest}
    want = {(c["clip"], cond, arm) for c in manifest for cond in ("clean", "noise") for arm in ARMS}
    have = {(r["clip"], r["condition"], r["arm"]) for r in results["runs"]}
    assert want == have, f"results.json misses {len(want - have)} runs and has {len(have - want)} extra"
    bad = sorted({r["clip"] for r in results["runs"] if r["clip_sha256"] != sha[r["clip"]]})
    assert not bad, f"clips changed after the eval ran: {bad[:5]}"
    table = render(summarise(results, items), meta)
    report = REPORT.read_text(encoding="utf-8").replace("\r\n", "\n")
    shown = report[report.index(TABLE_START): report.index(TABLE_END) + len(TABLE_END)]
    assert shown == table, "eval/asr/README.md table differs from results.json: rerun without --check"
    print(f"asr eval check OK: {len(manifest)} clips × 2 conditions × {len(ARMS)} prompts")


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("--limit must be at least 1")
    return value


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=_positive, default=None, help="first N clips only; prints, writes nothing")
    args = ap.parse_args()
    if args.check:
        return check()
    results = run(args.limit)
    table = render(summarise(results, load_items()), results["meta"])
    if results["meta"]["complete"]:
        RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        REPORT.write_text(replace_table(REPORT.read_text(encoding="utf-8"), table), encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
