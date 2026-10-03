"""変換済みのデータから、GitHub リリースに付けるファイル一式を作る(#42)。

使い方: python scripts/build_release.py <tag> --kunijiban-date <YYYY-MM-DD> --dpp-date <YYYY-MM-DD>
  例:   python scripts/build_release.py data-2026.09 --kunijiban-date 2026-09-27 --dpp-date 2026-09-26

入力(既定のパス):
  build/japan.{borings,layers,spt}.ndjson   boring-convert の出力
  data/kunijiban/japan/borings.ndjson       kunijiban_fetch.py の一覧(孔口に KuniJiban の code を足す)
  build/dpp.points.ndjson                   dpp_points.py の出力
  viewer/public/data/japan.mlt.pmtiles、japan-dpp-points.mlt.pmtiles

出力: dist/<tag>/ に GeoParquet 4 本、PMTiles 2 本、README.md、SHA256SUMS。
アップロードはしない。最後に表示する gh release create のコマンドを手で実行する。

データには独自のライセンスを付けない(KuniJiban 利用規約 第 4 条で著作権の設定が禁止されているため)。
出典・規約の文面は docs/release-README.md で管理する。
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from string import Template

import geopandas as gpd
import pyarrow.parquet as pq

from dpp_client import ROOT

# (出力ファイル名, 入力 NDJSON, 並べ替えのキー)
TABLES = [
    ("kunijiban-borings.parquet", "japan.borings.ndjson", ["boring_id"]),
    ("kunijiban-layers.parquet", "japan.layers.ndjson", ["boring_id", "layer_index"]),
    ("kunijiban-spt.parquet", "japan.spt.ndjson", ["boring_id", "depth_cm"]),
    ("dpp-points.parquet", "dpp.points.ndjson", ["dpp_id"]),
]
TILES = ["japan.mlt.pmtiles", "japan-dpp-points.mlt.pmtiles"]


def read_ndjson(path):
    g = gpd.read_file(path, engine="pyogrio")
    # 欠損のある整数列は float64 で読まれるので、null を許す整数型に戻す
    for col in g.columns.drop("geometry"):
        s = g[col]
        if s.dtype.kind == "f" and (s.dropna() % 1 == 0).all():
            g[col] = s.astype("Int64" if s.abs().max() >= 2**31 else "Int32")
    return g


def write_geoparquet(g, path):
    g.to_parquet(path, compression="zstd", schema_version="1.1.0", write_covering_bbox=False)
    # geopandas は geometry 列に Arrow の拡張型 geoarrow.wkb を付け、その中に CRS を PROJJSON の文字列で入れる。
    # GDAL 3.12(QGIS 4.0 に同梱)はこちらを優先して読み、CRS を読めずに「不明」にする(3.9 と 3.13 は読める)。
    # GeoParquet の CRS はファイルの geo メタデータにあるので、列の拡張型は外す
    t = pq.read_table(path)
    i = t.schema.get_field_index("geometry")
    t = t.set_column(i, t.schema.field(i).remove_metadata(), t.column(i))
    pq.write_table(t, path, compression="zstd")


def count_lines(path):
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tag", help="リリースのタグ(例 data-2026.09)")
    ap.add_argument("--kunijiban-date", required=True, help="KuniJiban から XML を取得し終えた日")
    ap.add_argument("--dpp-date", required=True, help="DPP からメタデータを取得した日")
    ap.add_argument("--build", default=str(ROOT / "build"))
    ap.add_argument("--kunijiban-list", default=str(ROOT / "data" / "kunijiban" / "japan" / "borings.ndjson"))
    ap.add_argument("--tiles", default=str(ROOT / "viewer" / "public" / "data"))
    ap.add_argument("--out", default=str(ROOT / "dist"))
    args = ap.parse_args()

    build = Path(args.build)
    out = Path(args.out) / args.tag
    if out.exists():
        raise SystemExit(f"{out} が既にある。リリースの中身は変えない方針なので、消すか別のタグにする")
    out.mkdir(parents=True)

    # KuniJiban の ID → code(DPP の点と code で突き合わせられるようにする。#27)
    codes = {}
    with open(args.kunijiban_list, encoding="utf-8") as f:
        for line in f:
            v = json.loads(line)
            codes[str(v["id"])] = v["code"]

    counts = {}
    for name, src, keys in TABLES:
        path = build / src
        g = read_ndjson(path)
        n = count_lines(path)
        if len(g) != n:
            raise SystemExit(f"{src}: 読み込んだ件数 {len(g):,} が行数 {n:,} と合わない")
        if name == "kunijiban-borings.parquet":
            g.insert(1, "code", g["boring_id"].map(codes))
            if g["code"].isna().any():
                raise SystemExit(f"code が見つからない孔がある: {g.loc[g['code'].isna(), 'boring_id'].head().tolist()}")
        g = g.sort_values(keys, kind="stable").reset_index(drop=True)
        write_geoparquet(g, out / name)
        counts[name] = len(g)
        print(f"{name}: {len(g):,} 件、{(out / name).stat().st_size / 1e6:.1f} MB")

    for name in TILES:
        shutil.copy2(Path(args.tiles) / name, out / name)
        print(f"{name}: {(out / name).stat().st_size / 1e6:.1f} MB")

    files = [name for name, _, _ in TABLES] + TILES
    sizes = {name: f"{(out / name).stat().st_size / 1e6:,.1f} MB" for name in files}
    template = Template((ROOT / "docs" / "release-README.md").read_text(encoding="utf-8"))
    (out / "README.md").write_text(template.substitute(
        tag=args.tag,
        kunijiban_date=args.kunijiban_date,
        dpp_date=args.dpp_date,
        n_borings=f"{counts['kunijiban-borings.parquet']:,}",
        n_layers=f"{counts['kunijiban-layers.parquet']:,}",
        n_spt=f"{counts['kunijiban-spt.parquet']:,}",
        n_dpp=f"{counts['dpp-points.parquet']:,}",
        **{f"size_{i}": sizes[name] for i, name in enumerate(files)},
    ), encoding="utf-8", newline="\n")

    with open(out / "SHA256SUMS", "w", encoding="utf-8", newline="\n") as f:
        for name in files + ["README.md"]:
            f.write(f"{sha256(out / name)}  {name}\n")

    print(f"\n完了: {out}\nアップロードするときは:")
    print(f'  gh release create {args.tag} --title "{args.tag}" --notes-file {out / "README.md"} '
          f'"{out}"/*.parquet "{out}"/*.pmtiles "{out}/README.md" "{out}/SHA256SUMS"')


if __name__ == "__main__":
    main()
