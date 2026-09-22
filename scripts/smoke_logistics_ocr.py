"""Explicit optional OCR smoke on a generated fixture; not a real-document benchmark."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from PIL import Image, ImageDraw, ImageFont
    from packing_assistant.logistics.intake import parse_document
    from packing_assistant.logistics.ledger import summarize
    folder = ROOT / "output" / "logistics-ocr-smoke"
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (2400, 800), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    font = ImageFont.truetype(str(font_path), 30) if font_path.is_file() else ImageFont.load_default(size=30)
    draw.text((55, 45), "SYNTHETIC PACKING LIST - OCR TEST ONLY", fill="black", font=font)
    headers = ["箱号", "材料编号", "品名", "箱数", "件数", "每箱件数", "单位", "净重 kg", "毛重 kg", "重量口径"]
    rows = [headers, ["A001", "MAT001", "钢板", "2", "10", "5", "件", "100", "110", "每箱"],
            ["A002", "MAT002", "型材", "3", "12", "4", "件", "80", "90", "每箱"]]
    x0, y0, width, height = 55, 170, 229, 130
    for row_index, row in enumerate(rows):
        for column, value in enumerate(row):
            x, y = x0 + column * width, y0 + row_index * height
            draw.rectangle((x, y, x + width, y + height), outline="black", width=3)
            draw.text((x + 13, y + 45), value, fill="black", font=font)
    draw.text((55, 650), "Synthetic fixture. No design dimensions supplied.", fill="black", font=font)
    path = folder / "synthetic-packing-list.png"
    image.save(path)
    document = parse_document(path.read_bytes(), path.name, ocr_backend="paddleocr")
    (folder / "recognized.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    result = summarize(document)
    print(json.dumps({"rows": document["rows"], "summary": result}, ensure_ascii=False), flush=True)
    assert len(document["rows"]) == 2, "Expected two source material rows"
    for row, expected in zip(document["rows"], [(2, 10, 100, 110), (3, 12, 80, 90)]):
        assert tuple(row[key] for key in ("package_count", "quantity", "net_kg", "gross_kg")) == expected, row
        assert row["length_mm"] == "UNSPECIFIED", "Missing dimensions must remain unknown"
        assert any(value.get("source", {}).get("bbox") for value in row["evidence"].values()), "Source coordinates required"
    print("SYNTHETIC_OCR_SMOKE_OK - real packing-list acceptance remains pending", flush=True)


if __name__ == "__main__":
    main()
