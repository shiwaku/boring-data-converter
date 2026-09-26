"""国土地盤情報検索サイト(KuniJiban)から、範囲内のボーリング柱状図 XML を取得する。

使い方: python scripts/kunijiban_fetch.py <name> <west> <south> <east> <north>
  例:   python scripts/kunijiban_fetch.py tokyo23 139.56 35.52 139.92 35.82

1. ビューアのマーカーAPI(ズーム13のタイル単位)で範囲内のボーリングIDを集める
   -> data/kunijiban/<name>/borings.ndjson
2. ID ごとに XML をダウンロードする(取得済みはスキップ。中断しても再実行で続きから)
   -> data/kunijiban/<name>/xml/<id>.xml、XML が無い ID は missing.txt に記録

利用規約: https://www.kunijiban.pwri.go.jp/jp/terms.html
第三者に提供する場合は「国土地盤情報検索サイト(KuniJiban)の地盤情報」である旨を表示すること。
"""
import json
import math
import os
import sys
import time

import requests

from dpp_client import ROOT

BASE = "https://www.kunijiban.pwri.go.jp/viewer/"
Z = 13  # ビューアがマーカーを取得するズーム(SETUP.borings.markers.minZoom)
RPS = float(os.getenv("KUNIJIBAN_RPS", "1"))

if len(sys.argv) != 6:
    raise SystemExit(__doc__)
name = sys.argv[1]
west, south, east, north = map(float, sys.argv[2:])
OUT = ROOT / "data" / "kunijiban" / name
(OUT / "xml").mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers["User-Agent"] = "boring-data-converter/0.1"
_last = 0.0


def get(url, **params):
    global _last
    for attempt in range(5):
        wait = 1.0 / RPS - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        try:
            r = session.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r
            err = f"HTTP {r.status_code}"
            if r.status_code not in (429, 500, 502, 503, 504):
                raise RuntimeError(err)
        except requests.RequestException as e:
            err = str(e)
        print(f"  retry {attempt + 1}/5 ({err})")
        time.sleep(min(60, 2 ** attempt))
    raise RuntimeError(f"giving up: {url} {params}")


def tile(lon, lat):
    n = 2 ** Z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


# 1. ID 一覧
borings_path = OUT / "borings.ndjson"
if not borings_path.exists():
    x0, y0 = tile(west, north)
    x1, y1 = tile(east, south)
    tiles = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    borings = {}
    for i, (x, y) in enumerate(tiles, 1):
        values = get(BASE + "server/markers.php", x=x, y=y, z=Z).json()["data"]["values"]
        for v in values:
            if west <= float(v["longitude"]) <= east and south <= float(v["latitude"]) <= north:
                borings[v["id"]] = v
        print(f"tile {i}/{len(tiles)} z{Z}/{x}/{y}: {len(values)} 件 (累計 {len(borings):,})")
    tmp = borings_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for v in borings.values():
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    tmp.replace(borings_path)
ids = [json.loads(line)["id"] for line in borings_path.open(encoding="utf-8")]
print(f"ボーリング {len(ids):,} 件")

# 2. XML
missing_path = OUT / "missing.txt"
missing = set(missing_path.read_text().split()) if missing_path.exists() else set()
todo = [i for i in ids if not (OUT / "xml" / f"{i}.xml").exists() and str(i) not in missing]
print(f"XML 取得対象 {len(todo):,} 件(取得済み・XMLなしを除く)")
for n, bid in enumerate(todo, 1):
    r = get(BASE + "refer/", data="boring", type="xml", id=bid)
    if "xml" not in r.headers.get("Content-Type", ""):
        # XML が無い ID は 200 + HTML のエラーページ(Error Code 404)が返る
        missing.add(str(bid))
        with missing_path.open("a") as f:
            f.write(f"{bid}\n")
    else:
        tmp = OUT / "xml" / f"{bid}.tmp"
        tmp.write_bytes(r.content)
        tmp.replace(OUT / "xml" / f"{bid}.xml")
    if n % 50 == 0 or n == len(todo):
        print(f"{n:,}/{len(todo):,} (XMLなし {len(missing):,})")
print(f"完了: {OUT}")
