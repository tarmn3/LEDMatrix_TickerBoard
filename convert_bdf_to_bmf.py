#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_bdf_to_bmf.py
  – bdflib で misaki_gothic.bdf を丸ごとパースし、
    JIS第2水準相当まで全グリフを
    スプライトシート経由で misaki_gothic.bmf に変換
"""

from pathlib import Path
import math
from PIL import Image
from bdflib import reader
from luma.core.bitmap_font import load_sprite_table

# 1) BDF 読み込み
SRC = Path("misaki_gothic.bdf")
if not SRC.exists():
    raise FileNotFoundError(f"{SRC} が見つかりません。")

with SRC.open("rb") as fp:
    bdf = reader.read_bdf(fp)

# 2) 有効なグリフ列を抽出 (幅・高さ >0, CP>=0x20)
glyphs = []
for g in bdf.glyphs:
    cp = g.codepoint
    if cp is None or cp < 0x20:
        continue
    xoff, yoff, w, h = g.get_bounding_box()
    if w > 0 and h > 0:
        glyphs.append(g)

if not glyphs:
    raise RuntimeError("有効なグリフが見つかりませんでした。")

# 3) 全グリフの最大セル幅・高さを求める
cell_w = max(g.get_bounding_box()[2] for g in glyphs)
cell_h = max(len(g.data) for g in glyphs)

# 4) シート配置を計算
count   = len(glyphs)
cols    = int(math.ceil(math.sqrt(count)))
rows    = int(math.ceil(count / cols))
sheet_w = cols * cell_w
sheet_h = rows * cell_h

# 5) スプライトシートを作成し各グリフを貼り付け
sheet = Image.new("1", (sheet_w, sheet_h))
for idx, g in enumerate(glyphs):
    xoff, yoff, w, h = g.get_bounding_box()
    char_img = Image.new("1", (cell_w, cell_h))
    for y, row_mask in enumerate(g.data):
        for x in range(w):
            if (row_mask >> (w - 1 - x)) & 1:
                # MAX7219での座標基準に合わせてグリフドットを上下反転する
                char_img.putpixel((x, cell_h - 1 - y), 1)
    cx = (idx % cols) * cell_w
    cy = (idx // cols) * cell_h
    sheet.paste(char_img, (cx, cy))

# 6) コードポイント順リストを作成
index = [g.codepoint for g in glyphs]

# 7) load_sprite_table でフォント化
font = load_sprite_table(
    sheet,
    index=index,
    xwidth=cell_w,
    glyph_size=(cell_w, cell_h),
    cell_size=(cell_w, cell_h)
)

# 8) .bmf として保存
out = SRC.with_suffix(".bmf")
font.save(str(out))
print("全グリフ変換完了:", out, f"({count} glyphs, {cols}×{rows} grid)")
