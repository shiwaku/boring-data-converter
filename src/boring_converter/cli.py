"""BED*.XML を GeoJSON Feature の NDJSON(1 行 1 フィーチャ)に変換する CLI。

    boring-convert <XML ファイルまたはディレクトリ>... -o build/tokyo23

出力(-o で指定した接頭辞に付く):
  <prefix>.layers.ndjson    土質層 1 層 = 1 フィーチャ
  <prefix>.spt.ndjson       標準貫入試験 1 回 = 1 フィーチャ
  <prefix>.borings.ndjson   ボーリング 1 本 = 1 フィーチャ

ジオメトリは孔口の Point(経度・緯度)。深度・標高は整数 cm の属性として持つ
(tippecanoe → mlt convert で float 属性が文字列列になる問題を避けるため)。
標高は孔口標高から深度を引いた値で、孔口標高が無いボーリングでは null。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bed import Boring, parse
from .soil import classify


def cm(v: float | None) -> int | None:
    return None if v is None else int(round(v * 100))


def feature(b: Boring, props: dict) -> str:
    return json.dumps({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(b.lon, 7), round(b.lat, 7)]},
        "properties": {"boring_id": b.id, **props},
    }, ensure_ascii=False)


def elev_cm(b: Boring, depth_m: float) -> int | None:
    return None if b.elevation_m is None else cm(b.elevation_m - depth_m)


def layer_features(b: Boring):
    for i, layer in enumerate(b.layers):
        yield feature(b, {
            "layer_index": i,
            "top_depth_cm": cm(layer.top_m),
            "bottom_depth_cm": cm(layer.bottom_m),
            "thickness_cm": cm(layer.bottom_m - layer.top_m),
            "top_elev_cm": elev_cm(b, layer.top_m),
            "bottom_elev_cm": elev_cm(b, layer.bottom_m),
            "soil_name": layer.name,
            "soil_symbol": layer.symbol,
            "soil_class": classify(layer.name),
            "color_name": layer.color,
        })


def spt_features(b: Boring):
    for s in b.spts:
        yield feature(b, {
            "depth_cm": cm(s.depth_m),
            "elev_cm": elev_cm(b, s.depth_m),
            "blows": s.blows,
            "penetration_cm": s.penetration_cm,
            "n_value": s.n_value,
        })


def boring_feature(b: Boring):
    return feature(b, {
        "name": b.name,
        "survey_name": b.survey_name,
        "dtd_version": b.dtd_version,
        "elevation_cm": cm(b.elevation_m),
        "length_cm": cm(b.length_m),
        "water_level_cm": cm(b.water_level_m),
        "layer_count": len(b.layers),
        "spt_count": len(b.spts),
    })


def iter_inputs(paths):
    for p in map(Path, paths):
        if p.is_dir():
            yield from sorted(q for q in p.rglob("*") if q.suffix.lower() == ".xml")
        else:
            yield p


def main(argv=None):
    ap = argparse.ArgumentParser(prog="boring-convert", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="BED*.XML ファイルまたはディレクトリ")
    ap.add_argument("-o", "--out", required=True, help="出力ファイルの接頭辞(例: build/tokyo23)")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_ok = n_err = n_layers = n_spt = 0
    with open(f"{out}.layers.ndjson", "w", encoding="utf-8") as fl, \
         open(f"{out}.spt.ndjson", "w", encoding="utf-8") as fs, \
         open(f"{out}.borings.ndjson", "w", encoding="utf-8") as fb:
        for path in iter_inputs(args.inputs):
            try:
                b = parse(path)
            except Exception as e:  # 壊れた XML は飛ばして続ける
                n_err += 1
                print(f"skip {path}: {e}", file=sys.stderr)
                continue
            for w in b.warnings:
                print(f"warn {path}: {w}", file=sys.stderr)
            fb.write(boring_feature(b) + "\n")
            for line in layer_features(b):
                fl.write(line + "\n")
                n_layers += 1
            for line in spt_features(b):
                fs.write(line + "\n")
                n_spt += 1
            n_ok += 1
    print(f"ボーリング {n_ok:,} 本(失敗 {n_err:,})、土質層 {n_layers:,}、標準貫入試験 {n_spt:,} -> {out}.*.ndjson")


if __name__ == "__main__":
    main()
