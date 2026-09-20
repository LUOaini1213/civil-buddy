"""What the user said, taken apart: clauses, labelled values, quantities, people, dates, rows.

The post writers used to cut a request on "；" and newlines and take one number per piece, or to
recognise a field only as a "标签：值" line. An ordinary sentence -
"螺纹钢 HRB400 本周入库 35 吨，领用 12 吨，盘点差 0.3 吨，仓管员张伟" - then became one table cell
holding the sentence, beside a row of TBD.

Nothing here infers, converts or computes. Every value returned is a literal stretch of the user's
text, trimmed - so the number-provenance guard keeps holding, and a draft still only says what the
user said. What is not found is simply absent; the writer keeps its TBD / [A001] for it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

_UNITS = (
    "立方米", "平方米", "万元", "亿元", "千克", "公斤", "公里", "延米", "工日", "台班", "小时", "分钟",
    "m³", "m3", "m²", "m2", "㎡", "mm", "cm", "km", "kg", "kW", "kw", "KW", "kVA", "KVA", "MPa", "kPa", "kN", "min",
    "吨", "方", "米", "根", "件", "块", "张", "台", "套", "个", "只", "支", "袋", "包", "箱", "桶", "车", "次", "人", "天", "日",
    "元", "升", "组", "批", "份", "页", "项", "层", "栋", "跨", "孔", "榀", "扇", "樘", "处", "道", "遍", "名", "位", "班", "周",
    "月", "年", "盘", "卷", "捆", "片", "节", "段", "口", "座", "辆", "m", "t", "g", "h", "L", "%", "％", "℃",
)
_UNIT_RE = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
# A number that is a quantity: not the digits of HRB400 / C35 / Φ20 / 3#楼 / DN100 / 2026-09-18 / GB 50010.
_QUANTITY = re.compile(
    r"(?<![A-Za-z0-9#＃Φφ.\-/:：_])(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)(?![\d.]|\s*[#＃])\s*(?P<unit>" + _UNIT_RE + r")?"
    r"(?![A-Za-z])"
)
_DATE = re.compile(
    r"\d{4}\s*[-/.年]\s*\d{1,2}\s*[-/.月]\s*\d{1,2}\s*日?|\d{1,2}\s*月\s*\d{1,2}\s*[日号]|\d{4}\s*年\s*\d{1,2}\s*月"
)
# Standard numbers and chainage carry digits that are not quantities either: GB 50010-2010, JGJ 130, K3+200.
_CODE = re.compile(
    r"(?:GB|JGJ|JTG|CJJ|JTS|SL|TB|DL|DB\d{0,2}|BS|EN|SS|ISO|ASTM|ACI|AISC)(?:/T)?\s*[A-Z]?\s*\d+(?:[.\-—]\d+)*"
    r"|[A-Z]{0,3}K\d+\s*\+\s*\d+(?:\.\d+)?"
)
_SURNAMES = (
    "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤常温康施文牛樊葛邢安齐易乔伍庞颜倪庄聂章鲁岳翟殷詹申欧耿关兰焦俞左柳甘祝包宁尚符舒阮柯纪梅童凌毕单季裴霍涂成苗谷盛曲翁冉骆蓝路游辛靳管柴蒙鲍华喻祁蒲房滕屈饶解牟艾尤阳时穆农司卓古吉缪简车项连芦麦褚娄窦戚岑景党宫费卜冷晏席卫米柏宗瞿桂全佟应臧闵苟邬边卞姬师和仇栾隋商刁沙荣巫寇桑郎甄丛仲虞敖巩明佘池查麻苑迟邝"
)
_PERIOD = re.compile(r"本周|上周|下周|本月|上月|下月|今天|今日|昨天|昨日|明天|明日|本季度|本年度|上午|下午|夜间|白班|夜班")
_SPEC = re.compile(
    r"(?:HRB|HPB|CRB|Q|C|M|P\.?[OSCPF]|DN|De|PN|Φ|φ|Ф)\s?\d+(?:\.\d+)?[A-Za-z]?(?:[-×xX*/]\d+(?:\.\d+)?)*"
    r"|\d+(?:\.\d+)?\s?[×xX*]\s?\d+(?:\.\d+)?(?:\s?[×xX*]\s?\d+(?:\.\d+)?)?(?:mm|cm|m)?"
)
_COMMAND = re.compile(
    r"^\s*(?:请|麻烦|帮我|帮忙|给我|替我|我要|我想|需要)?\s*(?:帮我|帮忙)?\s*"
    r"(?:写|出|做|起草|编|编制|整理|生成|列|填|拟|弄|搞|准备|登记|更新|汇总)(?:一下|一份|一个|一张|份|个|张|下)?"
    r"[^，,。；;：:\n]{0,24}?[：:，,]\s*"
)
_CONNECT = r"[\s：:＝=为是约共计达有了的]*"
_CLAUSE_SPLIT = re.compile(r"[\n；;。，]|,(?!\d{3}(?!\d))")
_ITEM_SPLIT = re.compile(r"[\n；;。]")
_NAME_EDGE = " \t，,;；。、:：-—（）()"


@dataclass(frozen=True)
class Quantity:
    number: str  # as written: "35", "1,200", "0.3"
    unit: str  # as written, "" when the user gave none
    start: int
    end: int

    @property
    def text(self) -> str:
        return f"{self.number}{self.unit}"


def strip_command(text: str) -> str:
    """Drop a leading imperative ("帮我写一份仓库台账：") so it is not read as an object's name."""
    return _COMMAND.sub("", text or "", count=1)


def clauses(text: str) -> List[str]:
    """Comma- and line-level pieces, in order. A thousands comma does not split."""
    return [piece.strip() for piece in _CLAUSE_SPLIT.split(text or "") if piece.strip()]


def items(text: str) -> List[str]:
    """Line- and sentence-level pieces: one object (with its follow-on clauses) is usually one item."""
    return [piece.strip() for piece in _ITEM_SPLIT.split(text or "") if piece.strip()]


def _masked(text: str) -> str:
    """The text with dates, standard numbers and chainage blanked out, same length: not quantities."""
    blank = lambda m: " " * len(m.group(0))  # noqa: E731
    return _CODE.sub(blank, _DATE.sub(blank, text))


def quantities(text: str) -> List[Quantity]:
    found = []
    for match in _QUANTITY.finditer(_masked(text or "")):
        found.append(Quantity(match.group("num"), match.group("unit") or "", match.start(), match.end()))
    return found


def dates(text: str) -> List[str]:
    return [re.sub(r"\s+", "", m.group(0)) for m in _DATE.finditer(text or "")]


def periods(text: str) -> List[str]:
    return [m.group(0) for m in _PERIOD.finditer(text or "")]


def specs(text: str) -> List[str]:
    """Grade / size tokens as written: HRB400, C35, Φ20, DN100, 600×300."""
    return [m.group(0).strip() for m in _SPEC.finditer(text or "")]


def _keyword_hit(text: str, keywords: Iterable[str]) -> Optional[Tuple[int, int]]:
    best: Optional[Tuple[int, int]] = None
    for keyword in keywords:
        at = text.find(keyword)
        if at >= 0 and (best is None or at < best[0] or (at == best[0] and at + len(keyword) > best[1])):
            best = (at, at + len(keyword))
    return best


def quantity_for(clause: str, keywords: Sequence[str], *, reach: int = 8) -> Optional[Quantity]:
    """The quantity a keyword introduces ("入库 35 吨", "领用了12t"), else the one right before it ("35吨入库")."""
    hit = _keyword_hit(clause, keywords)
    if hit is None:
        return None
    found = quantities(clause)
    after = [q for q in found if q.start >= hit[1]]
    if after and after[0].start - hit[1] <= reach and not _keyword_between(clause, hit[1], after[0].start):
        return after[0]
    before = [q for q in found if q.end <= hit[0]]
    if before and hit[0] - before[-1].end <= 1:
        return before[-1]
    return None


def _keyword_between(clause: str, start: int, end: int) -> bool:
    return bool(re.search(r"[一-鿿]{3,}", clause[start:end]))


def column_quantities(clause: str, columns: Mapping[str, Sequence[str]], *, reach: int = 8) -> Dict[str, Quantity]:
    """Which quantity in this clause belongs to which column.

    The longest keyword wins a position ("盘点差" is not "盘点"), a quantity goes to the keyword
    right before it, and a keyword or a quantity is used once - so "入库 35 吨 出库 12 吨" is two
    columns, never 35 in both.
    """
    table = sorted(((alias, key) for key, names in columns.items() for alias in names), key=lambda p: -len(p[0]))
    taken = [False] * len(clause)
    hits: List[Tuple[int, int, str]] = []
    for alias, key in table:
        for match in re.finditer(re.escape(alias), clause):
            start, end = match.span()
            if not any(taken[start:end]):
                for i in range(start, end):
                    taken[i] = True
                hits.append((start, end, key))
    hits.sort()
    found = quantities(clause)
    used: set = set()
    result: Dict[str, Quantity] = {}
    for index, (start, end, key) in enumerate(hits):
        if key in result:
            continue
        limit = hits[index + 1][0] if index + 1 < len(hits) else len(clause)
        after = [q for q in found if end <= q.start < limit and q.start not in used]
        if after and after[0].start - end <= reach and not _keyword_between(clause, end, after[0].start):
            result[key] = after[0]
            used.add(after[0].start)
            continue
        before = [q for q in found if q.end <= start and q.start not in used]
        if before and start - before[-1].end <= 1:
            result[key] = before[-1]
            used.add(before[-1].start)
    return result


def labelled(text: str, aliases: Mapping[str, Sequence[str]]) -> Dict[str, str]:
    """{key: value} for every alias the user wrote a value after, in lines or in running text.

    "冷负荷：850 kW" / "冷负荷 850kW，新风量 12000 m³/h" / "冷负荷为850kW". A value runs to the next
    alias or to the end of its clause; after "标签：" at the start of a line it runs to the end of
    the line, commas included, unless another "标签：" follows on that line. First mention wins.
    """
    table = sorted(((alias, key) for key, names in aliases.items() for alias in names), key=lambda p: -len(p[0]))
    values: Dict[str, str] = {}
    for line in (text or "").splitlines():
        hits: List[Tuple[int, int, str, bool]] = []
        taken = [False] * len(line)
        for alias, key in table:
            for match in re.finditer(re.escape(alias), line):
                start, end = match.span()
                if any(taken[start:end]):
                    continue
                rest = line[end:]
                colon = bool(re.match(r"\s*[：:＝=]", rest))
                edge = start == 0 or line[start - 1] in " \t，,;；。、（(的"
                introduces = bool(re.match(r"\s*(?:[为是约共计]\s*)?[\dA-Za-zΦφ]", rest)) or (edge and bool(re.match(r"\s+\S", rest)))
                if not (colon or introduces):
                    continue
                for i in range(start, end):
                    taken[i] = True
                hits.append((start, end, key, colon))
        hits.sort()
        for index, (start, end, key, colon) in enumerate(hits):
            stop = hits[index + 1][0] if index + 1 < len(hits) else len(line)
            value = line[end:stop]
            whole_line = colon and not line[:start].strip(_NAME_EDGE)
            if not whole_line:
                cut = _CLAUSE_SPLIT.search(value)
                if cut:
                    value = value[:cut.start()]
            value = re.sub(r"^" + _CONNECT, "", value).strip(_NAME_EDGE)
            if value and key not in values:
                values[key] = value
    return values


def person_for(text: str, roles: Sequence[str]) -> str:
    """The name written with a role: "仓管员张伟", "负责人：李工", "张伟（仓管员）". Literal, or ""."""
    name = "[" + _SURNAMES + r"][一-鿿]{1,2}"  # a surname first: "仓管员今天请假" names nobody
    for role in sorted(roles, key=len, reverse=True):
        match = re.search(re.escape(role) + r"\s*(?:[：:是为]\s*)?(" + name + r")(?=[\s，,;；。、（(]|$)", text or "")
        if match:
            return match.group(1)
        match = re.search("(" + name + r")\s*[（(]\s*" + re.escape(role) + r"\s*[）)]", text or "")
        if match:
            return match.group(1)
    return ""


def object_rows(text: str, columns: Mapping[str, Sequence[str]], *, drop: Sequence[str] = ()) -> List[Dict[str, str]]:
    """Ledger-like requests as rows: one per object the user named, each column from its own clause.

    "螺纹钢 HRB400 入库 35 吨，领用 12 吨；水泥 P.O 42.5 入库 80 吨" -> two rows. A clause that names
    nothing new ("领用 12 吨") belongs to the object before it, never to the next one - that is
    what keeps one material's number out of another's row. A row carries "name", "spec" and
    "period" when the user gave them, only the columns the user gave, and "source": the stretch of
    the request it came from, for a writer to look up that row's own labels and people in.
    """
    rows: List[Dict[str, str]] = []
    every = [k for names in columns.values() for k in names]
    for item in items(strip_command(text)):
        current: Optional[Dict[str, str]] = None
        for clause in clauses(item):
            hit = _keyword_hit(clause, every)
            found_here = column_quantities(clause, columns)
            if hit is None and not found_here:
                continue  # a clause with no column in it names nothing: "仓管员张伟" is not a material
            head = clause[: hit[0]] if hit else ""
            name, spec = _object_name(head, drop)
            if name or spec:
                current = {"name": name or spec, "source": item}
                if spec and name:
                    current["spec"] = spec
                when = periods(clause) + dates(clause)
                if when:
                    current["period"] = when[0]
                rows.append(current)
            if current is None:
                continue
            for key, quantity in found_here.items():
                current.setdefault(key, quantity.text)
    return rows


def _object_name(head: str, drop: Sequence[str]) -> Tuple[str, str]:
    """(name, spec) from the words before the first column keyword; ("", "") when they name nothing."""
    cleaned = _PERIOD.sub(" ", _masked(head))
    for word in drop:
        cleaned = cleaned.replace(word, " ")
    spec = " ".join(specs(cleaned))
    name = re.sub(r"\s+", " ", _SPEC.sub(" ", cleaned)).strip(_NAME_EDGE)
    if len(name) > 30 or not re.search(r"[一-鿿A-Za-z]", name):
        name = ""
    return name, spec


def table_cell(value: str) -> str:
    """A user's words made safe for a Markdown table cell: one line, no cell break, no markup."""
    import html

    return html.escape(re.sub(r"\s*\n\s*", " ", str(value or "")).strip(), quote=False).replace("|", "&#124;")
