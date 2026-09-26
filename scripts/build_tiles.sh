#!/usr/bin/env bash
# boring-convert の NDJSON から MVT / MLT の PMTiles を作る。
#
#   bash scripts/build_tiles.sh build/tokyo23 tokyo23
#
# 入力: <prefix>.layers.ndjson、<prefix>.spt.ndjson、<prefix>.borings.ndjson
# 出力:
#   build/<name>.mvt.pmtiles              MVT(tippecanoe。MLT の変換元・比較用)
#   viewer/public/data/<name>.mlt.pmtiles MLT(mlt convert、tile_type = mlt。ビューワが読む)
# タイル内のレイヤー名は layers / spt / borings。
# 引いたズームでは孔口の点(borings)だけを入れ、土質層・標準貫入試験はズーム LAYER_MINZOOM 以上に入れる
# (「引いたら点、寄ったら層」。全国に広げたときに広域のタイルが巨大にならないようにするため)。
#
# 必要なもの: tippecanoe 2.17 以降、mlt CLI(cargo install mlt)。Linux / macOS / WSL で実行する。

set -euo pipefail

PREFIX=${1:?usage: build_tiles.sh PREFIX NAME}
NAME=${2:?usage: build_tiles.sh PREFIX NAME}
MINZOOM=${MINZOOM:-4}
LAYER_MINZOOM=${LAYER_MINZOOM:-11}
MAXZOOM=${MAXZOOM:-14}

export PATH="$HOME/.cargo/bin:$PATH"
for tool in tippecanoe mlt; do
  command -v "$tool" >/dev/null || { echo "$tool が見つかりません" >&2; exit 1; }
done

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DIST="${DIST:-$ROOT/viewer/public/data}"
BUILD="$ROOT/build"
mkdir -p "$DIST" "$BUILD"

# 1 本のボーリングは同じ座標に層の数だけ点が重なるので、間引くと柱の途中が欠ける。
#   -r1 / --no-feature-limit / --no-tile-size-limit で間引きを止める
#   --buffer=0 で隣のタイルに同じ点が重複して入らないようにする
# -T で属性の型を固定する(列の型を揃えるのが MLT の前提。数値は整数 cm)
INT_ATTRS=(
  layer_index top_depth_cm bottom_depth_cm thickness_cm top_elev_cm bottom_elev_cm
  depth_cm elev_cm blows penetration_cm n_value
  elevation_cm length_cm water_level_cm layer_count spt_count
)
TIPPE_OPTS=(
  -q --force
  -Z"$MINZOOM" -z"$MAXZOOM"
  -r1 --no-feature-limit --no-tile-size-limit --buffer=0
  --generate-ids
  -j "{\"layers\": [\">=\", \"\$zoom\", $LAYER_MINZOOM], \"spt\": [\">=\", \"\$zoom\", $LAYER_MINZOOM]}"
  -P
)
for a in "${INT_ATTRS[@]}"; do TIPPE_OPTS+=(--attribute-type="$a":int); done

echo "== 1/2 tippecanoe -> $BUILD/$NAME.mvt.pmtiles"
tippecanoe -o "$BUILD/$NAME.mvt.pmtiles" "${TIPPE_OPTS[@]}" \
  -L layers:"$PREFIX.layers.ndjson" \
  -L spt:"$PREFIX.spt.ndjson" \
  -L borings:"$PREFIX.borings.ndjson"

echo "== 2/2 mlt convert -> $DIST/$NAME.mlt.pmtiles"
# mlt convert は既存の出力に追記しようとして止まるので、先に消す
rm -f "$DIST/$NAME.mlt.pmtiles"
mlt convert --tile-compression gzip "$BUILD/$NAME.mvt.pmtiles" "$DIST/$NAME.mlt.pmtiles"

ls -l "$BUILD/$NAME.mvt.pmtiles" "$DIST/$NAME.mlt.pmtiles"
