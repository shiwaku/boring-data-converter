"""国土地盤情報検索サイト(KuniJiban)から、範囲内のボーリング柱状図 XML を取得する。

使い方: python scripts/kunijiban_fetch.py <name> <west> <south> <east> <north>
        python scripts/kunijiban_fetch.py <name> --all-japan
  例:   python scripts/kunijiban_fetch.py tokyo23 139.56 35.52 139.92 35.82

全国の取得は約 21 万リクエストになり、KuniJiban に大きな負荷がかかる。変換済みの全国分は
タイルで公開しているので(README「変換済みのデータ」)、まずそちらを使うこと。
どうしても全国分が要るときだけ --all-japan を付ける。

1. ビューアの検索 API(search.php、1 ページ 30 件)で範囲内のボーリングを集める
   -> data/kunijiban/<name>/borings.ndjson(ID・座標・調査名・XML の有無など)
   全国は 223,689 件・7,457 ページ(2026-09 時点)。ページ単位で再開できる
2. XML があるもの(boring_xml_url > 0)だけダウンロードする。取得済みはスキップし、中断しても
   再実行で続きから。XML が無いものにはリクエストを送らない
   -> data/kunijiban/<name>/xml/<id>.xml

どちらもリクエストは既定で 1 件/秒以下(環境変数 KUNIJIBAN_RPS)。429 や 5xx が返ったら待ち時間を延ばして再試行する。

利用規約: https://www.kunijiban.pwri.go.jp/jp/terms.html
第三者に提供する場合は「国土地盤情報検索サイト(KuniJiban)の地盤情報」である旨を表示すること。
"""
import json
import os
import sys
import time

import requests

from dpp_client import ROOT

BASE = "https://www.kunijiban.pwri.go.jp/viewer/"
# 大量取得でアクセスを止められた事例があるため、1 件/秒に抑える(#34)
RPS = float(os.getenv("KUNIJIBAN_RPS", "1"))
JAPAN = (122.0, 20.0, 154.0, 46.0)

if len(sys.argv) == 6:
    west, south, east, north = map(float, sys.argv[2:])
elif len(sys.argv) == 3 and sys.argv[2] == "--all-japan":
    west, south, east, north = JAPAN
else:
    raise SystemExit(__doc__)
name = sys.argv[1]
OUT = ROOT / "data" / "kunijiban" / name
(OUT / "xml").mkdir(parents=True, exist_ok=True)

session = requests.Session()
# 先方が問い合わせ先を分かるように、リポジトリの URL を入れる
session.headers["User-Agent"] = "boring-data-converter/0.1 (+https://github.com/shiwaku/boring-data-converter)"
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


# 1. 検索 API で一覧を集める(ページ単位で追記し、最後に取れたページを state に残す)
borings_path = OUT / "borings.ndjson"
state_path = OUT / "search.state.json"
bbox = f"{north},{west},{south},{east}"  # search.php は 北,西,南,東
if not borings_path.exists() or state_path.exists():
    state = json.loads(state_path.read_text()) if state_path.exists() else {"page": 0}
    if state["page"] == 0 and borings_path.exists():
        borings_path.unlink()
    page = state["page"] + 1
    with borings_path.open("a", encoding="utf-8") as f:
        while True:
            data = get(BASE + "server/search.php", bbox=bbox, page=page).json()["data"]
            for v in data["values"]:
                f.write(json.dumps(v, ensure_ascii=False) + "\n")
            f.flush()
            state_path.write_text(json.dumps({"page": page, "pages": data["meta"]["pages"]}))
            if page % 50 == 0 or page >= data["meta"]["pages"]:
                print(f"search {page:,}/{data['meta']['pages']:,} ページ(全 {data['meta']['total']:,} 件)")
            if page >= data["meta"]["pages"] or not data["values"]:
                break
            page += 1
    state_path.unlink()

borings = {}
for line in borings_path.open(encoding="utf-8"):
    v = json.loads(line)
    borings[v["id"]] = v  # ページの境目で重複しても 1 件にする
with_xml = [i for i, v in borings.items() if (v.get("boring_xml_url") or 0) > 0]
print(f"ボーリング {len(borings):,} 件(XML あり {len(with_xml):,} 件)")

# 2. XML
missing_path = OUT / "missing.txt"
missing = set(missing_path.read_text().split()) if missing_path.exists() else set()
todo = [i for i in with_xml if not (OUT / "xml" / f"{i}.xml").exists() and str(i) not in missing]
print(f"XML 取得対象 {len(todo):,} 件(取得済み・取得できなかったものを除く)")
for n, bid in enumerate(todo, 1):
    r = get(BASE + "refer/", data="boring", type="xml", id=bid)
    if "xml" not in r.headers.get("Content-Type", ""):
        # フラグがあっても XML が返らないもの(200 + HTML のエラーページ)は記録だけする
        with missing_path.open("a") as f:
            f.write(f"{bid}\n")
    else:
        tmp = OUT / "xml" / f"{bid}.tmp"
        tmp.write_bytes(r.content)
        tmp.replace(OUT / "xml" / f"{bid}.xml")
    if n % 100 == 0 or n == len(todo):
        print(f"xml {n:,}/{len(todo):,}")
print(f"完了: {OUT}")
