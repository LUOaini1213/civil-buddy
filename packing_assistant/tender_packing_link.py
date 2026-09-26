"""Tender <-> packing, in one run and kept linked: the tender's logistics clauses, a loading plan made from the
real panel list under those clauses, and the English statements that answer them.

The partner's problem, in its words: the tender response and the outbound packing "run as two disconnected
exercises and need to stay linked". Bid statements on packing were not tied to a loading plan, and container
counts were not tied to the clauses they should satisfy. This module is the tie:

  tender file ──> logistics clauses (clause no., kind, limit)      container type taken FROM the clause
  panel list  ──> pack_ship_solve.run_plan (the demo's own path: conservation check, needs-human gates)
  both        ──> one matrix row per clause check, with status and the plan figure behind it
              ──> the English bid-book logistics section: every statement cites its clause and figure; what the
                  plan cannot support is a marked placeholder for a named person
              ──> tender-packing-link.json: statement -> clause -> plan figures -> sha256 of tender, list, plan

On a re-run the new record is compared with the previous one: every earlier statement is reported as changed,
unchanged or withdrawn, and the inputs that moved are named. No statement is carried forward silently.

Not modelled, and so never "covered": securing / lashing to the CTU Code, A-frame stillages, upright transport,
no-stacking rules, delivery sequencing. A-frame stillage sizes and masses are not guessed. A plan that does not fit
(can_fit is not true: crates left out of the containers) evidences no type, count or mass. A person confirms the
plan before any booking; submit_blocked stays true.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA = "tender.packing_link.v1"
LINK_FILE = "tender-packing-link.json"
REPORT_FILE = "tender-packing-link.md"
BIDBOOK_FILE = "bidbook.en.md"
PLAN_FILE = "pack-plan.json"
DEFAULT_CONTAINER = "40HQ"

# kinds of logistics clause, in the order their statements are numbered (S1, S2, ...; "S" for statement, so they never read as the line references L7, L15 of the tender matrix)
KINDS = ("container_type", "containers_used", "gross_mass", "securing", "handling", "crate_structure", "delivery_sequence")
KIND_TITLE = {
    "container_type": "Container type",
    "containers_used": "Containers used",
    "gross_mass": "Gross mass per loaded container",
    "securing": "Cargo securing / lashing",
    "handling": "Handling: stillages, upright, stacking, protection",
    "crate_structure": "Crate / frame structure",
    "delivery_sequence": "Delivery sequence",
}
KIND_OWNER = {"container_type": "logistics", "containers_used": "logistics", "gross_mass": "logistics",
              "securing": "competent person (lashing)", "handling": "logistics", "crate_structure": "packing designer",
              "delivery_sequence": "project manager"}

_NO_L = r"(?<![A-Za-z])"
_NO_R = r"(?![A-Za-z])"
_CONTEXT_RE = re.compile(r"transport|deliver|ship|pack|container|cargo|load|stillage|haul|lorr(?:y|ies)|truck|vehicle|"
                         r"运输|包装|装柜|装箱|交货|发货|到货|集装箱|货物|货|柜", re.I)
_GROSS_RE = re.compile(r"gross\s+(?:mass|weight)|weight\s+limit|max(?:imum)?\.?\s+(?:gross\s+|cargo\s+)?(?:mass|weight)|"
                       r"payload|限重|总重|毛重|货载|超重|最大重量", re.I)
_MASS_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
                      r"(kg|kgs|kilograms?|tonnes?|tons?|t|公斤|千克|吨)(?![A-Za-z])", re.I)
_TARE_RE = re.compile(r"tare|including\s+the\s+container|含柜|柜重|箱体自重", re.I)
_CARGO_BASIS_RE = re.compile(r"payload|cargo\s+(?:mass|weight)|net\s+(?:mass|weight)|货重|货载|净重", re.I)
_SEQUENCE_RE = re.compile(r"sequenc|installation\s+programme|installation\s+program|delivery\s+schedule|just[\s-]in[\s-]time|"
                          r"call[\s-]off|按.{0,8}(?:顺序|进度)|分批|交货计划|到货计划", re.I)
_CRATE_RE = re.compile(_NO_L + r"(?:crat(?:e|es|ed|ing)|timber\s+cases?|wooden\s+cases?|steel\s+frames?|packing\s+cases?)"
                       + _NO_R + r"|木箱|铁架|钢架", re.I)
# what a handling clause asks for, in words a bid statement can use (tender_parse._PACK_UNMODELLED_RE finds them)
_HANDLING_LABELS = ((r"a[\s-]?frame|stillage", "A-frame stillages"), (r"upright|vertical|竖放|立放|直立|竖立", "upright transport"),
                    (r"stack|堆叠|叠放|堆码", "no stacking"), (r"protect|防护", "face protection"), (r"fragile|易碎", "fragile handling"),
                    (r"防潮|防雨", "weather protection"), (r"熏蒸", "fumigation"))
_CLAUSE_NO_RE = re.compile(r"^\s*(?:clause\s+)?(\d+(?:\.\d+){1,3})(?=[\s.:)])", re.I)
# a container size with no type code ("20-foot containers", "40' containers", "40尺柜"): 40 ft is a GP or an HQ, and
# the planner needs the type, so a clause like this is read as naming a container but not a type to plan in
_SIZE_ONLY_RE = re.compile(r"(?<![\w.])(20|40|45)\s*-?\s*(?:ft|foot|feet|['’]|尺|英尺)\.?(?:\s*[A-Za-z]+){0,2}?\s*(?:containers?|集装箱|柜)",
                           re.I)


# ---------------------------------------------------------------------------------------------------------
# tender -> logistics clauses

def _clause_units(text: str) -> List[Dict[str, Any]]:
    """The tender as clauses: (id, locator, text). A structured document gives its own clause numbers
    (tools/tender_document.py); plain text falls back to its line number."""
    from packing_assistant.tools import tender_document

    units: List[Dict[str, Any]] = []
    if tender_document.is_document(text or ""):
        doc = tender_document.read(text or "")
        grouped: Dict[Tuple[str, int], Dict[str, Any]] = {}
        for piece in doc.pieces:
            if piece.kind == "heading":
                continue
            key = (piece.ref, piece.line)
            unit = grouped.get(key)
            if unit is None:
                number = str(piece.number or "").strip()
                grouped[key] = unit = {"clause": number or f"L{piece.line}", "locator": piece.ref, "line": piece.line, "parts": []}
                units.append(unit)
            unit["parts"].append(piece.text.strip())
        for unit in units:
            unit["text"] = " ".join(p for p in unit.pop("parts") if p)
    else:
        n = 0
        for raw in (text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            n += 1
            numbered = _CLAUSE_NO_RE.match(line)
            units.append({"clause": numbered.group(1) if numbered else f"L{n}", "locator": f"L{n}", "line": n, "text": line})
    return [u for u in units if u.get("text")]


def _mass_values(text: str) -> List[float]:
    values = []
    for m in _MASS_RE.finditer(text):
        number = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        values.append(number * 1000.0 if unit in ("t", "tonne", "tonnes", "ton", "tons", "吨") else number)
    return values


def logistics_clauses(text: str) -> List[Dict[str, Any]]:
    """Every clause of the tender that sets a logistics requirement, with its kinds and what it states."""
    from packing_assistant.tools.tender_parse import _CONTAINER_RE, _LASHING_RE, _PACK_UNMODELLED_RE, _REFUSE_RE, _container_codes

    found: List[Dict[str, Any]] = []
    for unit in _clause_units(text):
        body = unit["text"]
        if body.lstrip().startswith("|") and not _container_codes(body):
            continue                                    # table rows: only a container code in them counts
        context = bool(_CONTEXT_RE.search(body))
        kinds: List[str] = []
        detail: Dict[str, Any] = {}
        codes = _container_codes(body)
        sizes = sorted({f"{m.group(1)} ft" for m in _SIZE_ONLY_RE.finditer(_CONTAINER_RE.sub(" ", body))})
        if codes or sizes:
            refused = set()
            # a code in a sentence that also says not / no / excluded: the sentence may refuse it ("20GP containers are
            # not accepted") or not ("40HQ containers, which shall not be stacked"); the tool does not decide which
            for sentence in re.split(r"(?<=[.;。；])\s*", body):
                if _REFUSE_RE.search(sentence):
                    refused |= _container_codes(sentence)
            kinds.append("container_type")
            detail.update(named=sorted(codes), refused=sorted(refused), allowed=sorted(codes - refused), sizes=sizes)
        masses = _mass_values(body)
        if _GROSS_RE.search(body) and masses and context:
            kinds.append("gross_mass")
            basis = "gross" if _TARE_RE.search(body) else "cargo" if _CARGO_BASIS_RE.search(body) else "unstated"
            detail.update(limits_kg=sorted(set(masses)), basis=basis)
        if _LASHING_RE.search(body) and context:
            kinds.append("securing")
            detail["securing_terms"] = sorted({m.group(0) for m in _LASHING_RE.finditer(body)}, key=str.lower)
        words = {m.group(0).lower() for m in _PACK_UNMODELLED_RE.finditer(body)}
        unmodelled = [label for pattern, label in _HANDLING_LABELS if any(re.search(pattern, w, re.I) for w in words)]
        if unmodelled and context:
            kinds.append("handling")
            detail["unmodelled"] = unmodelled
        if _CRATE_RE.search(body) and context:
            kinds.append("crating")
        if _SEQUENCE_RE.search(body) and context:
            kinds.append("delivery_sequence")
        if kinds:
            found.append({**unit, "kinds": kinds, **detail, "sha256": _sha(body.encode("utf-8"))})
    return found


_CHOOSE = "a person chooses the type and names it in the request (e.g. 'in 40HQ')"


def container_decision(clauses: Sequence[Dict[str, Any]], known: Optional[Sequence[str]] = None,
                       requested: Optional[str] = None) -> Dict[str, Any]:
    """Which container type the plan is made for, and why: the type the request names, else the tender's clause,
    else 40HQ by default - said so.

    A type the planner cannot model, several types, a size with no type ("40 ft containers") or a code in a sentence
    that also says not / no: no plan, a person decides - and says the type in the request. The planner's own list of
    types is the only list (pack_ship_solve.known_container_types)."""
    if known is None:
        from packing_assistant.tools.pack_ship_solve import known_container_types

        known = known_container_types()
    if requested:
        code = str(requested).strip().upper()
        tender = container_decision(clauses, known)
        if code not in known:
            return {"type": None, "source": "request", "clause": None, "named": code, "tender": tender,
                    "reason": f"The request names {code}; the planner can only model {', '.join(known)}. No plan was made."}
        same = tender.get("type") == code
        return {"type": code, "source": "request", "clause": tender.get("clause") if same else None, "tender": tender,
                "reason": f"Container type {code} named in the request"
                          + (f"; Clause {tender['clause']} names the same type." if same and tender.get("clause")
                             else f" (the ITT: {tender['reason']})")}
    naming = [c for c in clauses if "container_type" in c["kinds"]]
    if not naming:
        return {"type": DEFAULT_CONTAINER, "source": "default", "clause": None,
                "reason": f"No container type (20GP / 40GP / 40HQ / 45HQ / OT / FR) was found in the ITT; the plan uses "
                          f"{DEFAULT_CONTAINER}, the planner's default."}
    allowed = sorted({code for c in naming for code in c.get("allowed") or []})
    sizes = sorted({size for c in naming for size in c.get("sizes") or []})
    refs = ", ".join(c["clause"] for c in naming)
    if len(allowed) == 1 and not sizes:
        code = allowed[0]
        clause = next(c["clause"] for c in naming if code in (c.get("allowed") or []))
        if code not in known:
            return {"type": None, "source": "tender_clause", "clause": clause, "named": code,
                    "reason": f"Clause {clause} names {code}; the planner can only model {', '.join(known)}. No plan was made: "
                              "a person plans this container type."}
        return {"type": code, "source": "tender_clause", "clause": clause,
                "reason": f"Container type {code} taken from Clause {clause}."}
    if not allowed and sizes:
        refused = sorted({code for c in naming for code in c.get("refused") or []})
        return {"type": None, "source": "tender_clause", "clause": refs, "named": ", ".join(sizes + refused),
                "reason": f"Clause {refs} names {' / '.join(sizes)} containers without the type (GP or HQ) the planner needs. "
                          f"No plan was made: {_CHOOSE}."}
    if not allowed:
        refused = sorted({code for c in naming for code in c.get("refused") or []})
        return {"type": None, "source": "tender_clause", "clause": refs, "named": ", ".join(refused),
                "reason": f"Clause {refs} names {', '.join(refused)} in a sentence that also says not / no / excluded; the tool "
                          f"does not decide whether that allows or excludes it. No plan was made: {_CHOOSE}."}
    options = allowed + [s for s in sizes]
    return {"type": None, "source": "tender_clause", "clause": refs, "named": ", ".join(options),
            "reason": f"Clause {refs} names {', '.join(options)}; which one to plan for is a person's choice. No plan was made: "
                      f"{_CHOOSE}."}


# ---------------------------------------------------------------------------------------------------------
# plan figures

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plan_sha256(plan: Optional[Dict[str, Any]]) -> Optional[str]:
    if not plan:
        return None
    stable = {k: v for k, v in plan.items() if k not in ("elapsed_s",)}
    return _sha(json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8"))


def container_tare_kg(container_type: str) -> Optional[float]:
    """The container's tare from the in-repo knowledge base (approximate; the CSC plate on the box governs)."""
    from packing_assistant.knowledge import load_kb

    spec = (load_kb().get("containers") or {}).get(str(container_type or "").upper()) or {}
    if spec.get("tare_kg") is not None:
        return float(spec["tare_kg"])
    if spec.get("tare_ton_approx") is not None:
        return round(float(spec["tare_ton_approx"]) * 1000.0, 1)
    return None


def _kg(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:,.1f}".rstrip("0").rstrip(".") if number != int(number) else f"{int(number):,}"


def _rows_per_container(plan: Dict[str, Any], limit: int = 12) -> str:
    parts = []
    per = plan.get("per_container") or []
    for item in per[:limit]:
        rows = ", ".join(f"{row} x {n}" for row, n in (item.get("rows") or {}).items())
        parts.append(f"{item.get('container_no')}: {rows or '(no rows)'}")
    more = f"; (+{len(per) - limit} more in {PLAN_FILE})" if len(per) > limit else ""
    return "; ".join(parts) + more


# ---------------------------------------------------------------------------------------------------------
# the checks: one matrix row and one statement per (clause, kind)

def _check(kind: str, clause: Optional[Dict[str, Any]], status: str, text: str, figures: Dict[str, Any],
           note: str, placeholder: bool) -> Dict[str, Any]:
    ref = clause["clause"] if clause else None
    return {"key": f"{kind}@{ref or 'none'}", "kind": kind, "clause": ref, "locator": clause["locator"] if clause else None,
            "clause_text": clause["text"] if clause else None, "clause_sha256": clause["sha256"] if clause else None,
            "status": status, "text": text, "figures": figures, "note": note, "placeholder": placeholder,
            "owner": KIND_OWNER[kind]}


def _placeholder(owner: str, body: str) -> str:
    return f"[TO CONFIRM by {owner}: {body}]"


def build_checks(clauses: Sequence[Dict[str, Any]], decision: Dict[str, Any], plan: Optional[Dict[str, Any]],
                 panel_list: str) -> List[Dict[str, Any]]:
    """The rows of the logistics response. Never "covered" without a plan figure that shows it."""
    checks: List[Dict[str, Any]] = []
    solved = bool(plan and plan.get("ok") and plan.get("source") == "solver")
    # a plan that does not fit (can_fit is not true) leaves crates unplaced: it evidences no type, count or mass
    fits = solved and plan.get("can_fit") is True
    by_kind = {kind: [c for c in clauses if kind in c["kinds"]] for kind in ("container_type", "gross_mass", "securing",
                                                                              "handling", "crating", "delivery_sequence")}
    handling = by_kind["handling"]
    stillage_words = list(dict.fromkeys(w for c in handling for w in c.get("unmodelled") or []))
    unmodelled_packing = bool(handling)
    if decision.get("type") is None:
        no_plan_why = decision.get("reason")
    else:
        rows = [f"{r.get('id') or r.get('name')} ({r.get('reason')})" for r in (plan or {}).get("needs_human") or [] if isinstance(r, dict)]
        no_plan_why = (f"no plan ({(plan or {}).get('error') or 'not run'}): {(plan or {}).get('detail') or ''}".strip(": ")
                       + (f"; panel-list rows a person must fix first: {', '.join(rows[:6])}" + (" ..." if len(rows) > 6 else "")
                          if rows else ""))
    ctype = (plan or {}).get("container_type") if solved else decision.get("type")
    cons = (plan or {}).get("conservation") or {}
    per = (plan or {}).get("per_container") or []
    placed = sum(int(item.get("boxes") or 0) for item in per)
    no_fit_why = (f"the loading plan does not fit: {len(per)} x {ctype} containers hold {placed} of the {plan.get('n_boxes')} "
                  f"crates (tool lower bound N0 = {plan.get('n0')}, binding constraint {plan.get('binding_constraint')})"
                  if solved and not fits else "")
    if decision.get("source") == "request" and decision.get("type"):
        type_source = "the request"
    elif decision.get("source") == "tender_clause" and decision.get("type"):
        type_source = f"Clause {decision['clause']}"
    else:
        type_source = None

    # container type: one row per clause that names one; a default is its own row
    deciding = next((c for c in by_kind["container_type"] if c["clause"] == decision.get("clause")), None)
    for clause in by_kind["container_type"] or [None]:
        named = ", ".join((clause.get("named") or []) + (clause.get("sizes") or [])) if clause else ""
        if clause is None:
            figures = {"container_type": ctype, "source": decision.get("source")}
            if solved:
                why = (f"The ITT names no container type. The loading plan uses {ctype}, "
                       + ("the type named in the request. " if decision.get("source") == "request" else "the planner's default. "))
                checks.append(_check("container_type", None, "human_required",
                                     why + _placeholder("logistics", "container type to be offered"
                                                        + (f"; {no_fit_why}" if no_fit_why else "")),
                                     figures, decision["reason"], True))
            else:
                checks.append(_check("container_type", None, "human_required",
                                     _placeholder("logistics", f"container type; {no_plan_why}"), figures, no_plan_why, True))
            continue
        figures = {"clause_names": named, "plan_container_type": ctype if solved else None, "type_source": type_source,
                   "can_fit": plan.get("can_fit") if solved else None}
        if solved and not fits:
            checks.append(_check("container_type", clause, "gap",
                                 _placeholder("logistics", f"container type (Clause {clause['clause']} names {named}): {no_fit_why}; "
                                                           "re-plan before the type is offered"),
                                 figures, no_fit_why, True))
        elif solved and ctype in (clause.get("allowed") or []) and decision.get("type") == ctype:
            checks.append(_check("container_type", clause, "covered",
                                 f"Clause {clause['clause']}: the panels will be shipped in {ctype} containers. The loading plan "
                                 f"was computed for {ctype}, the type taken from {type_source}"
                                 + ("." if type_source == f"Clause {clause['clause']}" else f", which Clause {clause['clause']} also names."),
                                 figures, "plan container_type equals the type the clause names", False))
        elif solved:
            why = (f"Clause {clause['clause']} names {named}; the plan was made in {ctype}"
                   + (" (the engine changed the requested type)" if decision.get("type") and ctype != decision.get("type") else ""))
            checks.append(_check("container_type", clause, "human_required", _placeholder("logistics", why + "."), figures, why, True))
        else:
            checks.append(_check("container_type", clause, "human_required",
                                 _placeholder("logistics", f"container type (Clause {clause['clause']} names {named}). {no_plan_why}"),
                                 figures, no_plan_why, True))

    # containers used: the count, tied to the clause the type came from
    count_clause = deciding
    if solved:
        n, n0 = plan.get("containers_used"), plan.get("n0")
        types = sorted({t for item in plan.get("per_container") or [] for t in (item.get("box_types") or {})})
        figures = {"containers_used": n, "container_type": ctype, "n0": n0, "pieces": cons.get("pieces_in"),
                   "cargo_net_kg": cons.get("kg_in"), "panel_list": panel_list, "crates": plan.get("n_boxes"),
                   "can_fit": plan.get("can_fit")}
        where = f"Clause {count_clause['clause']}: t" if count_clause else "T"
        if not fits:
            # crates are left out of the containers: no count is stated, only why
            text = _placeholder("logistics", f"number of containers for the {cons.get('pieces_in')} items "
                                             f"({_kg(cons.get('kg_in'))} kg net) of panel list {panel_list}: {no_fit_why}; "
                                             "re-plan before any count is stated")
            checks.append(_check("containers_used", count_clause, "gap", text, figures, "the plan does not fit", True))
        else:
            text = (f"{where}he loading plan places the {cons.get('pieces_in')} items ({_kg(cons.get('kg_in'))} kg net) of panel list "
                    f"{panel_list} in {n} x {ctype} containers (tool lower bound N0 = {n0}); every piece and kilogram on the list is "
                    f"in a crate (conservation check {cons.get('pieces_in')} -> {cons.get('pieces_out')} pieces).")
            status, note, placeholder = "covered", "count from the loading plan", False
            if decision.get("type") and ctype != decision["type"]:
                status, note = "human_required", f"plan made in {ctype}, not the {decision['type']} asked for"
                text += " " + _placeholder("logistics", note)
                placeholder = True
            else:
                if unmodelled_packing:
                    refs = ", ".join(c["clause"] for c in handling)
                    text += (f" The count rests on the planner's own crate model ({plan.get('n_boxes')} crates, {len(types)} crate "
                             f"type{'s' if len(types) != 1 else ''}, listed in {PLAN_FILE}); "
                             + _placeholder("logistics", f"re-confirm the count once the packaging of Clause {refs} "
                                                         f"({', '.join(stillage_words)}) is sized - it is not modelled"))
                    status, note = "partial", f"crate model, not the packaging Clause {refs} asks for"
                if not count_clause:
                    # the type came from the request or the default, not from a clause the count could satisfy
                    status, note = "human_required", "no clause names the planned container type; the count answers no clause"
                    text += " " + _placeholder("logistics", f"the ITT does not name {ctype}; confirm the container type before "
                                                            "this count is stated")
                    placeholder = True
            checks.append(_check("containers_used", count_clause, status, text, figures, note, placeholder))
    else:
        checks.append(_check("containers_used", count_clause, "human_required",
                             _placeholder("logistics", f"number of containers. {no_plan_why}"), {"containers_used": None}, no_plan_why, True))

    # gross mass per loaded container, against each limit
    for clause in by_kind["gross_mass"]:
        limits = clause.get("limits_kg") or []
        basis = clause.get("basis")
        if not fits or not per:
            why = no_plan_why if not solved else no_fit_why or "the plan has no per-container figures"
            checks.append(_check("gross_mass", clause, "human_required",
                                 _placeholder("logistics", f"gross mass per container (Clause {clause['clause']}). {why}"),
                                 {"limit_kg": limits[0] if len(limits) == 1 else limits}, why, True))
            continue
        heaviest = max(per, key=lambda item: float(item.get("cargo_kg") or 0))
        cargo = float(heaviest.get("cargo_kg") or 0)
        tare = container_tare_kg(ctype)
        gross = round(cargo + tare, 1) if tare is not None else None
        figures = {"limit_kg": limits[0] if len(limits) == 1 else limits, "limit_basis": basis,
                   "heaviest_container_no": heaviest.get("container_no"), "max_cargo_kg": cargo, "container_tare_kg": tare,
                   "max_gross_kg": gross, "containers": len(per)}
        if len(limits) != 1 or tare is None:
            why = ("several mass figures in one clause: " + ", ".join(_kg(x) for x in limits)) if len(limits) != 1 else f"no tare for {ctype}"
            checks.append(_check("gross_mass", clause, "human_required",
                                 _placeholder("logistics", f"gross mass per container (Clause {clause['clause']}): {why}"), figures, why, True))
            continue
        limit = limits[0]
        compared = cargo if basis == "cargo" else gross
        label = "cargo mass (panels and crates)" if basis == "cargo" else "gross mass"
        head = (f"Clause {clause['clause']} limits the {'cargo' if basis == 'cargo' else 'gross'} mass of each loaded container to "
                f"{_kg(limit)} kg. The heaviest planned container (no. {heaviest.get('container_no')} of {len(per)}) carries "
                f"{_kg(cargo)} kg of panels and crates; with the {ctype} tare of {_kg(tare)} kg (knowledge base, approximate - the "
                f"container's CSC plate governs) its gross mass is {_kg(gross)} kg.")
        if compared > limit:
            if basis == "unstated" and cargo <= limit:
                why = "the clause does not say whether the limit includes the tare: cargo is within it, gross is not"
                checks.append(_check("gross_mass", clause, "human_required", head + " " + _placeholder("logistics", why), figures, why, True))
            else:
                over = round(compared - limit, 1)
                checks.append(_check("gross_mass", clause, "gap",
                                     head + f" The {label} exceeds the limit by {_kg(over)} kg: the plan does not meet Clause "
                                     f"{clause['clause']}. " + _placeholder("logistics", "re-plan before this statement can be made"),
                                     figures, f"over the limit by {_kg(over)} kg", True))
            continue
        margin = round(limit - compared, 1)
        figures["margin_kg"] = margin
        text = head + f" That is {_kg(margin)} kg under the limit" + (" (compared as gross, the stricter reading, because the clause does not say)" if basis == "unstated" else "") + "."
        if unmodelled_packing:
            refs = ", ".join(c["clause"] for c in handling)
            text += " " + _placeholder("logistics", f"the mass of the packaging of Clause {refs} and of dunnage is not included; confirm it fits "
                                                    f"within the {_kg(margin)} kg margin before the VGM is signed")
            checks.append(_check("gross_mass", clause, "partial", text, figures,
                                 f"within the limit by the plan's figures; packaging mass of Clause {refs} not modelled", False))
        else:
            text += " Dunnage and lashing material are not included; the shipper's signed VGM governs."
            checks.append(_check("gross_mass", clause, "covered", text, figures, "per-container figure within the limit", False))

    # not modelled: securing, handling, delivery sequence
    for clause in by_kind["securing"]:
        terms = ", ".join(clause.get("securing_terms") or [])
        figures = {"mid50": (plan or {}).get("mid50") if solved else None}
        checks.append(_check("securing", clause, "human_required",
                             _placeholder("a competent person", f"cargo securing / lashing ({terms}) to Clause {clause['clause']}. "
                                                                 "Not modelled by the planner: the lashing plan is designed and signed "
                                                                 "separately (the plan's mid50 is the centre of gravity only)"),
                             figures, "not modelled", True))
    for clause in handling:
        words = ", ".join(clause.get("unmodelled") or [])
        stillage = "A-frame stillages" in (clause.get("unmodelled") or [])
        checks.append(_check("handling", clause, "human_required",
                             _placeholder("logistics", f"{words} (Clause {clause['clause']}). Not modelled: "
                                          + ("the planner has no A-frame stillage size, tare or capacity, and " if stillage else "the planner ")
                                          + "does not model upright, no-stacking or protection rules"),
                             {"asks_for": words}, "not modelled", True))
    for clause in by_kind["delivery_sequence"]:
        figures = {"rows_per_container": _rows_per_container(plan) if solved else None}
        checks.append(_check("delivery_sequence", clause, "human_required",
                             _placeholder("the project manager", f"delivery sequence (Clause {clause['clause']}). Not modelled: the "
                                                                   "plan loads by packing, not by the installation programme"
                                                                   + (f" (plan: {figures['rows_per_container']})" if solved else "")),
                             figures, "not modelled", True))

    # crate structure: the plan's own verdict per crate; a pending design is a person's job, never a pass
    # (always one row, so a re-run without a plan names this statement as changed, not withdrawn)
    crate_clause = (by_kind["crating"] or handling or [None])[0]
    if not solved:
        checks.append(_check("crate_structure", crate_clause, "human_required",
                             _placeholder("the packing designer", f"crate structure. {no_plan_why}"),
                             {"n_boxes": None}, no_plan_why, True))
    else:
        st = plan.get("structure") or {}
        figures = {k: st.get(k) for k in ("n_boxes", "pass", "needs_reinforcement", "fail", "pending_design")}
        if st.get("n_boxes") and st.get("pass") == st.get("n_boxes") and unmodelled_packing:
            # the check is on the planner's own crates; the tender asks for packaging the planner does not model
            refs = ", ".join(c["clause"] for c in handling)
            checks.append(_check("crate_structure", crate_clause, "partial",
                                 f"All {st.get('n_boxes')} crates of the planner's own crate model pass its structural check. "
                                 + _placeholder("the packing designer", f"the packaging Clause {refs} asks for "
                                                                        f"({', '.join(stillage_words)}) is not modelled or checked"),
                                 figures, f"planner's crates pass; packaging of Clause {refs} not modelled", False))
        elif st.get("n_boxes") and st.get("pass") == st.get("n_boxes"):
            checks.append(_check("crate_structure", crate_clause, "covered",
                                 f"All {st.get('n_boxes')} crates pass the planner's structural check.", figures, "structure check", False))
        else:
            checks.append(_check("crate_structure", crate_clause, "human_required",
                                 _placeholder("the packing designer", f"crate structure - of {st.get('n_boxes')} crates, "
                                              f"{st.get('pending_design')} are pending detailed design (待详设), "
                                              f"{st.get('needs_reinforcement')} need reinforcement, {st.get('fail')} fail"),
                                 figures, "detailed design", True))
    order = {kind: i for i, kind in enumerate(KINDS)}
    checks.sort(key=lambda c: order[c["kind"]])
    for i, check in enumerate(checks, 1):
        check["id"] = f"S{i}"
        check["sha256"] = _sha(json.dumps([check["text"], check["figures"], check["clause_sha256"]], ensure_ascii=False,
                                          sort_keys=True, default=str).encode("utf-8"))
    return checks


# ---------------------------------------------------------------------------------------------------------
# stay linked: compare with the previous record

def compare(previous: Optional[Dict[str, Any]], current: Dict[str, Any],
            earlier_exports: Sequence[str] = ()) -> Optional[Dict[str, Any]]:
    """What moved since the previous record, statement by statement. None when there is no previous record.

    ``earlier_exports``: Word copies an earlier run left in the folder. A Word export never overwrites (a person may
    have edited it), so the old statements live on in them: they are named, not deleted."""
    if previous is None:
        return None
    if not isinstance(previous, dict) or previous.get("schema") != SCHEMA:
        ids = [s["id"] for s in current.get("statements") or []]
        return {"previous_generated_at": None, "inputs_changed": [{"input": "record", "label": "previous link record unreadable"}],
                "changed": [], "unchanged": [], "withdrawn": [], "new": [{"id": i, "key": s["key"]} for i, s in
                                                                       zip(ids, current.get("statements") or [])],
                "needs_reconfirmation": ids,
                "summary": "the previous link record could not be read: every statement (" + ", ".join(ids) + ") needs confirmation"}
    inputs = []
    for key, label in (("tender", "tender"), ("panel_list", "panel list"), ("plan", "plan")):
        old, new = (previous.get("inputs") or {}).get(key) or {}, (current.get("inputs") or {}).get(key) or {}
        if old.get("sha256") != new.get("sha256"):
            names = f" ({old.get('name')} -> {new.get('name')})" if old.get("name") != new.get("name") else ""
            inputs.append({"input": key, "label": label + names, "old_sha256": old.get("sha256"), "new_sha256": new.get("sha256")})
    old_by = {s["key"]: s for s in previous.get("statements") or []}
    new_by = {s["key"]: s for s in current.get("statements") or []}
    changed, unchanged, withdrawn, added = [], [], [], []
    moved: Dict[str, Tuple[Any, Any]] = {}
    for key, new in new_by.items():
        old = old_by.get(key)
        if old is None:
            added.append({"id": new["id"], "key": key})
            continue
        if old.get("sha256") == new.get("sha256"):
            unchanged.append({"id": new["id"], "key": key, "previous_id": old.get("id")})
            continue
        diffs = {k: [old.get("figures", {}).get(k), v] for k, v in (new.get("figures") or {}).items()
                 if old.get("figures", {}).get(k) != v}
        for k, pair in diffs.items():
            moved.setdefault(k, tuple(pair))
        changed.append({"id": new["id"], "key": key, "previous_id": old.get("id"), "figures": diffs,
                        "clause_changed": old.get("clause_sha256") != new.get("clause_sha256"),
                        "status": [old.get("status"), new.get("status")]})
    for key, old in old_by.items():
        if key not in new_by:
            withdrawn.append({"id": old.get("id"), "key": key, "text": old.get("text"),
                              "label": f"earlier {old.get('id')} ({KIND_TITLE.get(old.get('kind'), old.get('kind'))}, "
                                       + (f"Clause {old.get('clause')})" if old.get("clause") else "no clause)")})
    headline_keys = ("containers_used", "max_cargo_kg", "max_gross_kg", "pieces", "cargo_net_kg", "container_type", "limit_kg")
    figure_line = "; ".join(f"{k.replace('_', ' ')} {_kg(a)} -> {_kg(b)}" for k, (a, b) in moved.items() if k in headline_keys)
    recheck = [c["id"] for c in changed] + [a["id"] for a in added]
    # statement ids are renumbered per run: where one moved, say which earlier statement it answers
    named = [c["id"] + (f" (was {c['previous_id']})" if c.get("previous_id") and c["previous_id"] != c["id"] else "")
             for c in changed] + [f"{a['id']} (new)" for a in added]
    if not inputs:
        summary = f"no input changed since the previous run; {len(unchanged)} statements re-derived with the same figures"
    else:
        summary = ", ".join(i["label"] + " changed" for i in inputs)
        if figure_line:
            summary += f": {figure_line}"
        summary += ("; statements " + ", ".join(named) + " need re-confirmation") if named else "; no statement changed"
        if withdrawn:
            summary += "; withdrawn (remove from the bid): " + ", ".join(w["label"] for w in withdrawn)
        if earlier_exports:
            summary += "; earlier Word copies " + ", ".join(earlier_exports) + " still hold the previous statements - do not send them"
    return {"previous_generated_at": previous.get("generated_at"), "inputs_changed": inputs, "changed": changed,
            "unchanged": unchanged, "withdrawn": withdrawn, "new": added, "needs_reconfirmation": recheck,
            "stale_exports": list(earlier_exports) if inputs else [], "summary": summary}


# ---------------------------------------------------------------------------------------------------------
# matrix rows for the bid-book, and the English section

_STATUS_DEV = {"covered": "No Deviation", "partial": "Partial Deviation", "gap": "Negative Deviation",
               "human_required": "Pending SME", "pending": "To confirm"}


def matrix_rows(checks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for c in checks:
        rows.append({"req_id": c["key"], "title": f"{KIND_TITLE[c['kind']]} ({c['id']})", "category": "transport",
                     "item_kind": "logistics_clause", "requirement_ref": f"ITT {c['clause']}" if c["clause"] else "(no clause)",
                     "owner": c["owner"], "risk": "high", "requirement_type": "mandatory", "status": c["status"],
                     "proposal_location": f"§6 Logistics {c['id']}", "compliance_label": _STATUS_DEV.get(c["status"], "To confirm"),
                     "evidence": {"type": "packing_link", "figures": c["figures"], "note": c["note"]},
                     "snippets": [c["clause_text"]] if c["clause_text"] else [], "exact_text": c["clause_text"]})
    return rows


def _cell(value: Any) -> str:
    return str(value if value is not None else "—").replace("|", "/").replace("\n", " ")


def _figure_text(figures: Dict[str, Any]) -> str:
    return "; ".join(f"{k} = {_kg(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v}"
                     for k, v in figures.items() if v not in (None, "", [], {})) or "—"


def logistics_section(record: Dict[str, Any]) -> str:
    """Chapter 6 of the English bid-book, written from the plan. Each statement cites its clause and figure."""
    inputs = record["inputs"]
    decision = record["container"]
    lines = ["## 6. Logistics & Packing (linked to the loading plan)", "",
             "> DRAFT. Every statement below cites the ITT clause it answers and the loading-plan figure behind it "
             f"(`{LINK_FILE}`). Text in `[TO CONFIRM ...]` is not supported by the plan and waits for the named person. "
             "The plan is an internal draft: a person confirms it before any booking. Qualifications and price are not "
             "written here.", "",
             f"- Tender: `{inputs['tender']['name']}` (sha256 {inputs['tender']['sha256'][:12]})",
             f"- Panel list: `{inputs['panel_list']['name']}` (sha256 {inputs['panel_list']['sha256'][:12]})",
             f"- Loading plan: " + (f"`{PLAN_FILE}` (sha256 {inputs['plan']['sha256'][:12]})" if inputs["plan"]["sha256"] else "none - no plan was made"),
             f"- Container type: {decision['reason']}", ""]
    changes = record.get("changes_since_previous")
    if changes and changes.get("inputs_changed"):
        lines += [f"> **Changed since the previous run ({changes.get('previous_generated_at')}):** {changes['summary']}.", ""]
    lines += ["| Stmt | ITT clause | Check | Status | Plan figure |", "|---|---|---|---|---|"]
    for s in record["statements"]:
        lines.append(f"| {s['id']} | {_cell(s['clause'])} | {KIND_TITLE[s['kind']]} | {s['status']} | {_cell(_figure_text(s['figures']))} |")
    lines.append("")
    for s in record["statements"]:
        lines.append(f"**{s['id']} ({'Clause ' + s['clause'] if s['clause'] else 'no clause'}).** {s['text']}")
        lines.append("")
    return "\n".join(lines)


def _annex_a(record: Dict[str, Any]) -> str:
    plan = record.get("plan") or {}
    lines = ["## Annex A — Loading plan summary", ""]
    if not plan:
        return "\n".join(lines + ["No loading plan was made; see §6.", ""])
    for key in ("container_type", "containers_used", "n0", "can_fit", "n_boxes", "utilization", "weight_utilization", "mid50"):
        lines.append(f"- `{key}`: {plan.get(key)}")
    for item in plan.get("per_container") or []:
        lines.append(f"- container {item.get('container_no')}: {item.get('boxes')} crates, {_kg(item.get('cargo_kg'))} kg cargo "
                     f"(panels + crates), rows {', '.join(f'{r} x {n}' for r, n in (item.get('rows') or {}).items())}")
    return "\n".join(lines) + "\n"


def report_markdown(record: Dict[str, Any]) -> str:
    """The one-page link report: clauses, matrix, statements, what changed. For the bid and logistics leads."""
    lines = ["# Tender <-> packing link (internal draft)", "",
             "Not for submission (submit_blocked = true). A person confirms the loading plan before any booking.", "",
             "## Inputs", ""]
    for key in ("tender", "panel_list", "plan"):
        item = record["inputs"][key]
        lines.append(f"- {key}: {item.get('name') or '—'} · sha256 {item.get('sha256') or '—'}")
    lines += ["", f"Container type: {record['container']['reason']}", "", "## Logistics clauses found in the tender", ""]
    if not record["clauses"]:
        lines.append("- none: the tender states no logistics requirement the tool recognises; a person checks it.")
    for c in record["clauses"]:
        lines.append(f"- Clause {c['clause']} ({', '.join(c['kinds'])}): {c['text']}")
    lines += ["", "## Response matrix (logistics)", "", "| Stmt | Clause | Check | Status | Owner | Plan figure | Note |",
              "|---|---|---|---|---|---|---|"]
    for s in record["statements"]:
        lines.append(f"| {s['id']} | {_cell(s['clause'])} | {KIND_TITLE[s['kind']]} | {s['status']} | {s['owner']} | "
                     f"{_cell(_figure_text(s['figures']))} | {_cell(s['note'])} |")
    lines += ["", "## Statements", ""]
    lines += [f"- {s['id']}: {s['text']}" for s in record["statements"]]
    changes = record.get("changes_since_previous")
    lines += ["", "## Changes since the previous run", ""]
    if not changes:
        lines.append("- first run: no previous link record in this folder.")
    else:
        lines.append(f"- {changes['summary']}")
        for c in changes["changed"]:
            diffs = "; ".join(f"{k} {_kg(a)} -> {_kg(b)}" for k, (a, b) in c["figures"].items()) or "wording"
            was = f" (was {c['previous_id']})" if c.get("previous_id") and c["previous_id"] != c["id"] else ""
            lines.append(f"- {c['id']}{was} changed ({diffs}){' - its clause text changed' if c['clause_changed'] else ''}: re-confirm")
        for c in changes["new"]:
            lines.append(f"- {c['id']} is new: confirm")
        for c in changes["withdrawn"]:
            lines.append(f"- {c.get('label') or c['id']} withdrawn: remove it from the bid ({str(c.get('text') or '')[:120]})")
        if changes["unchanged"]:
            lines.append("- re-derived with the same figures: " + ", ".join(c["id"] for c in changes["unchanged"]))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------------------
# the run

def _read_tender(path: Path) -> str:
    from packing_assistant.office_job import DOCUMENT_FILE_CHARS, read_material_checked

    body, why = read_material_checked(path, DOCUMENT_FILE_CHARS)
    if why:
        raise ValueError(f"the tender {path.name} could not be read: {why}")
    return body


def earlier_exports(folder: str) -> List[str]:
    """Word copies of the link report and bid-book already in ``folder`` (from earlier runs)."""
    root = Path(folder) if folder else None
    if not root or not root.is_dir():
        return []
    stems = (Path(REPORT_FILE).stem, Path(BIDBOOK_FILE).stem)
    return sorted(p.name for p in root.glob("*.docx") if any(p.stem == s or p.stem.startswith(s + "-") for s in stems))


def run_link(tender_path: str, packing_list: str, *, previous: Optional[Dict[str, Any]] = None,
             project_name: str = "", now: Optional[str] = None, exports: Sequence[str] = (),
             container_type: Optional[str] = None) -> Dict[str, Any]:
    """ITT + panel list -> clauses, plan, matrix rows, statements, bid-book, link record (and what changed).

    ``container_type``: the type the request names, when a person chose it (the ITT names none, several, or a size
    only). It is planned as asked; a clause that names another type then reads human_required, never covered."""
    from packing_assistant.bidbook.sg_facade import build_sg_facade_bidbook
    from packing_assistant.tools.pack_ship_solve import plan_record_json, run_plan
    from packing_assistant.tools.tender_parse import (_count_by, _readiness_score, build_response_matrix, open_actions,
                                                      parse_tender_text)

    from packing_assistant.office_job import _resolve_job_file

    # both inputs through the job folder's read guard (inside the job root, no secrets), as every job-file read
    tender, table = _resolve_job_file(Path(tender_path)), _resolve_job_file(Path(packing_list))
    text = _read_tender(tender)
    clauses = logistics_clauses(text)
    decision = container_decision(clauses, requested=container_type)
    plan: Optional[Dict[str, Any]] = None
    if decision["type"]:
        plan = run_plan(file_path=str(table), container_type=decision["type"])
    solved = bool(plan and plan.get("ok") and plan.get("source") == "solver")
    checks = build_checks(clauses, decision, plan, table.name)
    record: Dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": now or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs": {"tender": {"name": tender.name, "sha256": _sha(tender.read_bytes())},
                   "panel_list": {"name": table.name, "sha256": _sha(table.read_bytes())},
                   "plan": {"name": PLAN_FILE if solved else None, "sha256": plan_sha256(plan) if solved else None}},
        "container": decision,
        "materials_source": "panel_list",
        "clauses": [{k: c[k] for k in ("clause", "locator", "kinds", "text", "sha256")} for c in clauses],
        "plan": ({k: plan.get(k) for k in ("container_type", "containers_used", "n0", "can_fit", "n_boxes", "utilization",
                                          "weight_utilization", "mid50", "per_container", "conservation", "structure")}
                 if solved else None),
        "plan_refusal": None if solved else {k: (plan or {}).get(k) for k in ("source", "error", "detail", "needs_human")} if plan else
                        {"source": "not_run", "error": "container_type_undecided", "detail": decision["reason"]},
        "statements": [{k: c[k] for k in ("id", "key", "kind", "clause", "locator", "clause_sha256", "status", "text",
                                          "figures", "note", "placeholder", "owner", "sha256")} for c in checks],
        "confirmed_by_person": False,
        "submit_blocked": True,
    }
    record["changes_since_previous"] = compare(previous, record, exports)

    parsed = parse_tender_text(text, source="tender-packing-link")
    reqs = list(parsed.get("requirements") or [])
    base = build_response_matrix(reqs, packing_summary=None)
    rows = [r for r in base["rows"] if r.get("category") not in ("transport", "packaging")] + matrix_rows(checks)
    summary = {"n": len(rows), **{s: sum(1 for r in rows if r["status"] == s)
                                  for s in ("covered", "partial", "pending", "human_required", "gap", "review")},
               "by_owner": _count_by(rows, "owner"), "by_risk": _count_by(rows, "risk")}
    summary["readiness_score"] = _readiness_score(summary)
    matrix = {"schema": "tender.response_matrix.v1", "tool": "tender.packing_link", "rows": rows, "summary": summary}
    bidbook = build_sg_facade_bidbook(tender_text=text, parsed=parsed, matrix=matrix, open_actions=open_actions(matrix),
                                      project_title=project_name or None, logistics_section=logistics_section(record),
                                      annex_a=_annex_a(record))
    deliverables = [{"name": REPORT_FILE, "text": report_markdown(record)},
                    {"name": BIDBOOK_FILE, "text": bidbook["markdown"]},
                    {"name": LINK_FILE, "text": json.dumps(record, ensure_ascii=False, indent=2) + "\n"}]
    if solved:
        deliverables.append({"name": PLAN_FILE, "text": plan_record_json(plan, table.name)})
    counts = {s: sum(1 for c in checks if c["status"] == s) for s in ("covered", "partial", "gap", "human_required")}
    reply = (f"Linked {tender.name} and {table.name}: {len(clauses)} logistics clauses, {len(checks)} statements "
             f"({counts['covered']} covered by the plan, {counts['partial']} partial, {counts['gap']} gap, "
             f"{counts['human_required']} for a person). "
             + (f"Plan {plan.get('containers_used')} x {plan.get('container_type')} ({decision['reason']}) "
                + ("" if plan.get("can_fit") is True else "DOES NOT FIT (can_fit is not true): no count or mass is stated. ")
                if solved
                else f"No plan: {decision['reason'] if not decision['type'] else (plan or {}).get('error')}. ")
             + (f"Since the previous run: {record['changes_since_previous']['summary']}. " if record["changes_since_previous"] else "")
             + "Internal draft, submit_blocked=true; a person confirms the plan before booking.")
    return {"ok": True, "schema": SCHEMA, "record": record, "statements": record["statements"], "matrix": matrix,
            "handoff": parsed.get("handoff"), "bidbook_markdown": bidbook["markdown"], "deliverables": deliverables,
            "plan": plan, "reply": reply, "submit_blocked": True}


def load_previous(path: str) -> Optional[Dict[str, Any]]:
    """The previous link record in the output folder, if any. An unreadable one is reported, not trusted."""
    target = Path(path) if path else None
    if not target or not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema": "unreadable"}
    return data if isinstance(data, dict) else None
