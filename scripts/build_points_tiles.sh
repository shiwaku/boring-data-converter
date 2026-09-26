#!/usr/bin/env bash
# DPP のメタデータから作った孔口の点(scripts/dpp_points.py)を MLT の PMTiles にする。
#
#   bash scripts/build_points_tiles.sh build/dpp.points.ndjson japan-dpp-points
#
# 出力:
#   build/<name>.mvt.pmtiles               MVT(tippecanoe。MLT の変換元)
#   viewer/public/data/<name>.mlt.pmtiles  MLT(ビューワが読む。全国分は R2 から配信する)
# タイル内のレイヤー名は dpp。
#
# 全国 26 万点を広域でも表示するため、引いたズームでは密な所を間引き(間引き率 DROP_RATE)、
# ベースズーム(-B)以上では全点を入れる。柱状図と違って点は 1 地点 1 つなので、間引いても表示は壊れない。
#
# 必要なもの: tippecanoe 2.17 以降、mlt CLI(cargo install mlt)。Linux / macOS / WSL で実行する。

set -euo pipefail

INPUT=${1:?usage: build_points_tiles.sh INPUT.ndjson NAME}
NAME=${2:?usage: build_points_tiles.sh INPUT.ndjson NAME}
MINZOOM=${MINZOOM:-4}
MAXZOOM=${MAXZOOM:-12}

export PATH="$HOME/.cargo/bin:$PATH"
for tool in tippecanoe mlt; do
  command -v "$tool" >/dev/null || { echo "$tool が見つかりません" >&2; exit 1; }
done

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DIST="${DIST:-$ROOT/viewer/public/data}"
BUILD="$ROOT/build"
mkdir -p "$DIST" "$BUILD"

INT_ATTRS=(dpp_id elevation_cm length_cm water_level_cm year has_xml)
TIPPE_OPTS=(
  -q --force
  -Z"$MINZOOM" -z"$MAXZOOM" -B"$MAXZOOM"
  -l dpp
  # 間引き率。既定(2.5)だと全国表示(z4)で 200 点ほどしか残らず疎すぎる
  -r"${DROP_RATE:-1.5}"
  --drop-densest-as-needed
  # 隣のタイルに同じ点が重複して入らないようにする
  --buffer=0
  --generate-ids
  -P
)
for a in "${INT_ATTRS[@]}"; do TIPPE_OPTS+=(--attribute-type="$a":int); done

echo "== 1/2 tippecanoe -> $BUILD/$NAME.mvt.pmtiles"
tippecanoe -o "$BUILD/$NAME.mvt.pmtiles" "${TIPPE_OPTS[@]}" "$INPUT"

echo "== 2/2 mlt convert -> $DIST/$NAME.mlt.pmtiles"
# mlt convert は既存の出力に追記しようとして止まるので、先に消す
rm -f "$DIST/$NAME.mlt.pmtiles"
mlt convert --tile-compression gzip "$BUILD/$NAME.mvt.pmtiles" "$DIST/$NAME.mlt.pmtiles"

ls -l "$BUILD/$NAME.mvt.pmtiles" "$DIST/$NAME.mlt.pmtiles"
