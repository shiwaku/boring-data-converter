"""DPP の国土地盤情報データベースのメタデータを、孔口の点(GeoJSON Feature の NDJSON)にする。

使い方: python scripts/dpp_points.py [data/metadata_ngi.ndjson] [-o build/dpp.points.ndjson]

XML が無くても全国のボーリングの位置を出すためのもの(利用条件は CC BY 4.0)。
深度・標高は boring-convert の出力と同じく整数 cm の属性にする。
"""
import argparse
import json
import re
from pathlib import Path

from dpp_client import ROOT


def cm(v):
    return None if v is None else int(round(float(v) * 100))


def soil_names(s):
    """「{シルト混じり砂,まさ土}」→「シルト混じり砂・まさ土」"""
    s = (s or "").strip().strip("{}")
    names = [n.strip().strip('"') for n in s.split(",") if n.strip().strip('"')]
    return "・".join(names) or None


def first(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", default=str(ROOT / "data" / "metadata_ngi.ndjson"))
    ap.add_argument("-o", "--out", default=str(ROOT / "build" / "dpp.points.ndjson"))
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(args.input, encoding="utf-8") as fi, out.open("w", encoding="utf-8") as fo:
        for line in fi:
            m = json.loads(line)["metadata"]
            name = (m.get("NGI:boring_name") or "").strip() or None
            survey = (m.get("NGI:survey_name") or "").strip() or None
            props = {
                "dpp_id": m["NGI:id"],
                "code": m.get("NGI:code"),
                "name": name,
                "survey_name": re.sub(r"\s+", " ", survey) if survey else None,
                "elevation_cm": cm(m.get("NGI:boring_elevation")),
                "length_cm": cm(m.get("NGI:boring_length")),
                "water_level_cm": cm(m.get("NGI:boring_waterlevel")),
                "soil_names": soil_names(m.get("NGI:rocksoil_names")),
                "year": int(m["DPF:year"]) if str(m.get("DPF:year") or "").isdigit() else None,
                "prefecture": first(m.get("DPF:prefecture_name")),
                # XML の有無(NGIC の XML は 2026-09 時点で取得できない。#5)
                "has_xml": 1 if m.get("NGI:link_boring_xml") else 0,
            }
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(float(m["NGI:longitude"]), 7),
                                                              round(float(m["NGI:latitude"]), 7)]},
                "properties": {k: v for k, v in props.items() if v is not None},
            }
            fo.write(json.dumps(feature, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n:,} 件 -> {out}")


if __name__ == "__main__":
    main()
