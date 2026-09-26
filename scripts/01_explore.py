"""DPP上の国土地盤情報のデータセットIDと、1件分のメタデータ・ファイル構成を確認する。

使い方: python scripts/01_explore.py [キーワード]   (既定: 地盤)
結果は explore/ に JSON で保存する。
"""
import json
import sys

from dpp_client import ROOT, DPPClient, gql_str

OUT = ROOT / "explore"
OUT.mkdir(exist_ok=True)
keyword = sys.argv[1] if len(sys.argv) > 1 else "地盤"
c = DPPClient()


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# 1. カタログ・データセット一覧から該当しそうなものを探す
catalogs = c.query("""
query { dataCatalog(IDs: null) { id title datasets { id title data_count } } }
""")["dataCatalog"]
save("catalogs.json", catalogs)

hits = []
for cat in catalogs:
    for ds in cat.get("datasets") or []:
        if keyword in (cat["title"] or "") or keyword in (ds["title"] or ""):
            hits.append((cat, ds))
            print(f"catalog={cat['id']} [{cat['title']}]  dataset={ds['id']} [{ds['title']}]  count={ds['data_count']}")
if not hits:
    raise SystemExit(f"'{keyword}' に一致するデータセットなし。explore/catalogs.json を確認してください")

# 2. 各データセットの先頭1件について、メタデータとファイル一覧を取る
for cat, ds in hits:
    res = c.query(f"""
query {{
  search(first: 0, size: 1, term: "", attributeFilter: {{ attributeName: "DPF:dataset_id", is: {gql_str(ds['id'])} }}) {{
    totalNumber
    searchResults {{ id title lat lon year dataset_id catalog_id }}
  }}
}}""")["search"]
    print(f"\n== {ds['id']} totalNumber={res['totalNumber']}")
    if not res["searchResults"]:
        continue
    rec = res["searchResults"][0]
    detail = c.query(f"""
query {{
  data(dataSetID: {gql_str(ds['id'])}, dataID: {gql_str(rec['id'])}) {{
    getDataResults {{ id title metadata files {{ id original_path }} }}
  }}
}}""")["data"]["getDataResults"][0]
    save(f"sample_{ds['id']}.json", detail)
    print(f"sample id={detail['id']} title={detail['title']}")
    for f in detail.get("files") or []:
        print(f"  file: {f['original_path']}")
    meta = detail.get("metadata") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    print("  metadata keys:", ", ".join(sorted(meta.keys())))
