"""ux(round8) PWA 最小件：生成 manifest 用的 PNG 图标（192/512）。

纯标准库（zlib+struct）写 PNG——零第三方依赖，零 CDN。图形 = 工程蓝圆角方块 + 白色
"CB" 位图字样（5x7 像素字形放大），与 demo/static/icons/cb-icon.svg 同款。
再运行：python scripts/gen_pwa_icons.py
"""
import struct
import zlib
from pathlib import Path

BLUE = (37, 99, 235, 255)    # --cb-blue #2563eb
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)

# "CB" 5x7 位图字形（C 与 B 并排，中间 1 列留白）
GLYPH = [
    ".###.#$$##",
    "#...##...#",
    "#....#...#",
    "#....####.",
    "#....#...#",
    "#...##...#",
    ".###.#$$##",
]
GLYPH_W, GLYPH_H = len(GLYPH[0]), len(GLYPH)


def rounded_filled(size: int, radius: int) -> list:
    """圆角方形 alpha 蒙版，返回 size*size 的 RGBA 像素列表。"""
    px = []
    for y in range(size):
        for x in range(size):
            inside = True
            for cx, cy in ((radius, radius), (size - 1 - radius, radius),
                           (radius, size - 1 - radius), (size - 1 - radius, size - 1 - radius)):
                if ((x < radius or x >= size - radius) and (y < radius or y >= size - radius)):
                    if (x - cx) ** 2 + (y - cy) ** 2 > radius ** 2:
                        inside = False
                        break
            px.append(BLUE if inside else CLEAR)
    return px


def stamp_glyph(px: list, size: int) -> None:
    """把 CB 字形按比例盖到画布中央（白色）。"""
    scale = max(2, int(size * 0.62 / GLYPH_H))
    gw, gh = GLYPH_W * scale, GLYPH_H * scale
    ox, oy = (size - gw) // 2, (size - gh) // 2
    for gy in range(GLYPH_H):
        for gx in range(GLYPH_W):
            if GLYPH[gy][gx] == "#":
                for dy in range(scale):
                    for dx in range(scale):
                        x, y = ox + gx * scale + dx, oy + gy * scale + dy
                        if 0 <= x < size and 0 <= y < size:
                            px[y * size + x] = WHITE


def write_png(path: Path, size: int) -> None:
    radius = size * 22 // 100
    px = rounded_filled(size, radius)
    stamp_glyph(px, size)
    raw = b"".join(b"\x00" + bytes(v for p in px[y * size:(y + 1) * size] for v in p)
                   for y in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    path.write_bytes(png)
    print(f"written {path} ({len(png)} bytes, {size}x{size})")


def main() -> None:
    for target in (Path("demo/static/icons"), Path("frontend/icons")):
        target.mkdir(parents=True, exist_ok=True)
        write_png(target / "cb-icon-192.png", 192)
        write_png(target / "cb-icon-512.png", 512)


if __name__ == "__main__":
    main()
