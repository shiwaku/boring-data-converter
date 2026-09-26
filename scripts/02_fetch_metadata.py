"""getAllData でデータセットの全件メタデータを取得し、NDJSON に書き出す。

使い方: python scripts/02_fetch_metadata.py <dataset_id>
出力:   data/metadata_<dataset_id>.ndjson (1行1レコード)
        data/metadata_<dataset_id>.state.json (再開用の次トークン)

中断しても同じコマンドを再実行すれば、保存済みトークンから続きを取得する。
トークンが失効して再開できない場合は state と ndjson を消して最初からやり直す。
"""
import json
import sys

from dpp_client import ROOT, DPPClient, gql_str

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
dataset_id = sys.argv[1]
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True)
ndjson = OUT / f"metadata_{dataset_id}.ndjson"
state = OUT / f"metadata_{dataset_id}.state.json"

token = json.loads(state.read_text())["next"] if state.exists() else None
if token is None and ndjson.exists():
    raise SystemExit(f"{ndjson} は既にあります(取得済み、または state なし)。取り直すなら削除して再実行してください")

c = DPPClient()
n = sum(1 for _ in ndjson.open(encoding="utf-8")) if ndjson.exists() else 0
with ndjson.open("a", encoding="utf-8") as f:
    while True:
        if token:
            args = f"size: 1000, nextDataRequestToken: {gql_str(token)}"
        else:
            args = (f'size: 1000, term: "", '
                    f'attributeFilter: {{ attributeName: "DPF:dataset_id", is: {gql_str(dataset_id)} }}')
        page = c.query(f"""
query {{
  getAllData({args}) {{
    nextDataRequestToken
    data {{ id title metadata }}
  }}
}}""")["getAllData"]
        rows = page.get("data") or []
        for row in rows:
            if isinstance(row.get("metadata"), str):
                row["metadata"] = json.loads(row["metadata"])
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        n += len(rows)
        token = page.get("nextDataRequestToken")
        # ndjson を flush してからトークンを保存する(異常終了しても取りこぼしが出ないように)
        state.write_text(json.dumps({"next": token, "count": n}))
        print(f"{n:,} 件")
        if not token or not rows:
            break

state.unlink()
print(f"完了: {n:,} 件 -> {ndjson}")
