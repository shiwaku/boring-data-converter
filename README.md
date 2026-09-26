# boring-data-converter

ボーリング柱状図 XML(地質・土質調査成果電子納品要領のボーリング交換用データ `BED*.XML`)を、
深度区間(土質層)ごとに 1 フィーチャの NDJSON(GeoJSON Feature)に変換し、3D で可視化するためのツールです。

> 開発中です。取得・変換・タイル化・3D ビューワが動きます(東京 23 区周辺で検証中)。

- デモ: <https://shiwaku.github.io/boring-data-converter/>(東京 23 区周辺、取得途中のデータ)
- 検討メモ: [docs/design-memo.md](docs/design-memo.md)

## 構成

```
取得(scripts/)       →  変換(src/boring_converter/)  →  タイル化(scripts/build_tiles.sh)  →  可視化(viewer/)
KuniJiban / DPP          XML → NDJSON(深度区間ごと)      NDJSON → MVT → MLT(PMTiles)          MapLibre + deck.gl
```

| パス | 内容 |
| --- | --- |
| `scripts/` | XML・メタデータの取得(KuniJiban、国土交通データプラットフォーム) |
| `src/boring_converter/` | XML → NDJSON コンバーター本体(`boring-convert` コマンド) |
| `viewer/` | 3D ビューワ(Vite + TypeScript、MapLibre GL JS 6 + deck.gl) |
| `tests/` | テストとサンプル XML(`tests/fixtures/`) |
| `docs/` | 設計・検討メモ |

## インストール

必要なもの: Python 3.12 以降。

```sh
pip install -e .            # コンバーターのみ
pip install -e ".[fetch]"   # 取得スクリプトも使う場合
```

## 変換

```sh
boring-convert data/kunijiban/tokyo23/xml -o build/tokyo23
```

XML ファイルまたはディレクトリ(再帰的に `*.xml` を探す)を複数指定できます。壊れた XML は飛ばし、警告とともに標準エラーに出します。

### 出力

| ファイル | 内容 |
| --- | --- |
| `<prefix>.layers.ndjson` | 土質層 1 層 = 1 フィーチャ |
| `<prefix>.spt.ndjson` | 標準貫入試験 1 回 = 1 フィーチャ |
| `<prefix>.borings.ndjson` | ボーリング 1 本 = 1 フィーチャ |

ジオメトリはいずれも孔口の Point(経度・緯度、世界測地系)です。深度・標高は **整数 cm** の属性で持ちます
(tippecanoe が数値を値ごとに sint / float / double で書き分け、`mlt convert` がそれを文字列列にしてしまうのを避けるため)。
標高は孔口標高から深度を引いた値で、孔口標高が無いボーリングでは `null` です。

| 属性 | ファイル | 内容 |
| --- | --- | --- |
| `boring_id` | 全部 | XML のファイル名(拡張子なし)。KuniJiban から取得した場合は KuniJiban の ID |
| `layer_index` | layers | 上から 0 始まり |
| `top_depth_cm` / `bottom_depth_cm` / `thickness_cm` | layers | 層の上端・下端の深度、層厚 [cm] |
| `top_elev_cm` / `bottom_elev_cm` | layers | 層の上端・下端の標高 [cm] |
| `soil_name` / `soil_symbol` / `color_name` | layers | 土質名、土質記号、色調(色調は層の中央深度で対応づけ) |
| `soil_class` | layers | 土質名の大分類(下表)。可視化の色分け用 |
| `depth_cm` / `elev_cm` | spt | 試験開始深度と標高 [cm] |
| `blows` / `penetration_cm` / `n_value` | spt | 合計打撃回数、合計貫入量、30 cm 換算の N 値(貫入量 30 cm 未満は 打撃回数 × 30 / 貫入量) |
| `name` / `survey_name` / `dtd_version` | borings | ボーリング名、調査名、XML の版 |
| `elevation_cm` / `length_cm` / `water_level_cm` | borings | 孔口標高、総掘進長、孔内水位(孔口からの深さ) [cm] |

### 土質の大分類(`soil_class`)

柱状図の土質名は自由記述で表記の揺れが大きい(東京 23 区の 645 本で 326 種類)ため、対応表ではなく規則で分類します([soil.py](src/boring_converter/soil.py))。

1. 次の語を含む名前は優先して分類します: 表土 → `topsoil`、盛土・埋土・砕石・舗装など → `fill`、岩 → `rock`、ローム・火山灰・スコリア・軽石 → `volcanic`、腐植・泥炭・有機質〜 → `organic`。
   ただし「火山灰混り砂」「有機質土混りシルト」のような「〜混り」は修飾として 2. に回します。
2. それ以外は、名前の中で最後に現れる土質の語で決めます(日本語は後ろが主体: 砂質シルト → `silt`、シルト質砂 → `sand`、砂礫 → `gravel`)。

| コード | 表示名 | 例 |
| --- | --- | --- |
| `topsoil` | 表土 | 表土、旧表土 |
| `fill` | 盛土・埋土 | 盛土、埋土、盛土(砂質シルト)、砕石、アスファルト |
| `organic` | 有機質土 | 高有機質土(腐植土)、有機質シルト |
| `volcanic` | 火山灰質土(ローム) | ローム、火山灰質粘性土、スコリア |
| `clay` | 粘性土 | 粘土、粘性土、砂質粘性土 |
| `silt` | シルト | シルト、砂質シルト、粘土質シルト |
| `sand` | 砂 | 砂、細砂、シルト質砂、砂利・礫混り砂 |
| `gravel` | 礫 | 礫、砂礫、礫質土、玉石混じり砂礫 |
| `rock` | 岩 | 泥岩、軟岩・風化岩、岩盤 |
| `unknown` | 不明 | 土質名が空 |

### 対応している版

| 版 | 土質層のタグ | 確認状況 |
| --- | --- | --- |
| 2.x | `土質岩種区分` | 2.10 で確認 |
| 3.00 | `岩石土区分` | 確認済み |
| 4.00 | `工学的地質区分名現場土質名`(総掘進長は `総削孔長`) | 確認済み |

- 測地系コードが `0`(日本測地系)の座標は、世界測地系に近似変換します(誤差数 m 程度)。
- 土質名が空の層(2.x に多い)は推測で埋めず `null` のままにします。
- Shift_JIS 宣言の XML は機種依存文字を含むことが多いため CP932 として読みます。

## タイル化

```sh
# WSL / Linux / macOS。tippecanoe 2.17 以降と mlt CLI(cargo install mlt)が必要
bash scripts/build_tiles.sh build/tokyo23 tokyo23
```

`viewer/public/data/<name>.mlt.pmtiles`(ビューワが読む MLT)と `build/<name>.mvt.pmtiles`(変換元の MVT)を出力します。
タイル内のレイヤーは `layers`(土質層)、`spt`(標準貫入試験)、`borings`(孔口)で、ズームは 8〜14 です。

- 1 本のボーリングは同じ座標に層の数だけ点が重なるため、間引くと柱の途中が欠けます。`-r1 --no-feature-limit --no-tile-size-limit` で間引きを止め、`--buffer=0` で隣のタイルへの重複を避けています。
- 東京 23 区周辺 868 本(土質層 9,812)で、MVT 3.5 MB → MLT 1.4 MB。全ズームで地物数が入力と一致することを確認しています。

## ビューワ

```sh
cd viewer
npm install
npm run dev      # http://127.0.0.1:5176
npm run build    # 型チェック → ../app/ へビルド
```

`main` に `viewer/` の変更を push すると、GitHub Actions(`.github/workflows/deploy-pages.yml`)がビルドして GitHub Pages に公開します。

| 機能 | 内容 |
| --- | --- |
| 柱状図 | 土質層ごとに色分けした円柱。**地下**(孔口を地面に置き実深度で下へ)/ **標高で比較**(T.P. で高さをそろえる)/ **地上に立てる** を切り替え。鉛直強調・半径を可変 |
| 土質 | 大分類 9 区分の凡例。クリックで表示・非表示 |
| ポップアップ | 円柱をクリックするとその孔の全層(深度・土質名)と、KuniJiban の柱状図 PDF へのリンク |
| 地形 | [Mapterhorn](https://mapterhorn.com/) の陰影起伏と 3D 地形(起伏倍率可変、最初からオン)。3D 地形のときの「地下」表示は地形越しに透かして描く |
| 背景地図 | 淡色 / 標準(地理院 最適化ベクトルタイル)/ 写真 / 白図、ライト / ダークテーマ |

- タイルの取得は MapLibre の MLT ソース(`encoding: "mlt"`)に任せ、読み込まれた地物を `querySourceFeatures` で拾って deck.gl の `ColumnLayer` で円柱にします。MapLibre の MLT デコーダは z を捨てるため、深度・標高は属性で運んでいます([jma-earthquake-data-converter](https://github.com/shiwaku/jma-earthquake-data-converter) の震源の立体表示と同じ構成)。
- 背景地図・テーマ・パネルは [naisui-risk-verification](https://github.com/shiwaku/naisui-risk-verification) の viewer を土台にしています。
- maplibre-gl 6 と deck.gl 9.3 の組み合わせでは `map.transform` の別名定義と `setWorkerUrl` が必要です(`viewer/src/main.ts` のコメント参照)。luma.gl は `overrides` で 9.3.6 に揃えています。

## 取得

### KuniJiban(XML)

[国土地盤情報検索サイト KuniJiban](https://www.kunijiban.pwri.go.jp/) から、範囲内のボーリング柱状図 XML を取得します。

```sh
# 名前と範囲(西 南 東 北)を指定。data/kunijiban/<name>/ に保存
python scripts/kunijiban_fetch.py tokyo23 139.56 35.52 139.92 35.82
```

ビューアのマーカー API(ズーム 13 のタイル単位)で ID を集め、XML を 1 件ずつダウンロードします。
サーバー負荷に配慮して既定 1 リクエスト/秒(環境変数 `KUNIJIBAN_RPS`)です。中断しても再実行で続きから取得します。

### 国土交通データプラットフォーム(メタデータ)

[国土交通データプラットフォーム(DPP)](https://www.mlit-data.jp/) API から、国土地盤情報データベースの全件メタデータ(262,284 件、2026 年 9 月時点)を取得します。
API キーはリポジトリ直下の `apikey.txt`(キーのみ 1 行)または `.env`(`MLIT_API_KEY=...`)に置きます。どちらも `.gitignore` 済みです。

```sh
python scripts/01_explore.py              # データセット ID と 1 件分の構成を確認
python scripts/02_fetch_metadata.py ngi   # 全件を data/metadata_ngi.ndjson に取得
```

DPP のメタデータにある XML の URL は国土地盤情報センター(`publicweb.ngic.or.jp`)を指していますが、2026 年 9 月時点でアクセスできない(HTTP 403)ため、XML の取得には KuniJiban を使っています。

## データの出典

| 用途 | データ | 提供元 | 備考 |
| --- | --- | --- | --- |
| 土質層タイル(`viewer/public/data/`) | 国土地盤情報検索サイト「KuniJiban」のボーリング柱状図 XML(東京 23 区周辺) | 国土交通省、国立研究開発法人土木研究所、国立研究開発法人港湾空港技術研究所 | [KuniJiban 利用規約](https://www.kunijiban.pwri.go.jp/jp/terms.html)に基づき加工・頒布 |
| サンプル XML(`tests/fixtures/`) | 国土地盤情報検索サイト「KuniJiban」のボーリング柱状図 XML(ID 149789321、243720635、506957380、508177590) | 国土交通省、国立研究開発法人土木研究所、国立研究開発法人港湾空港技術研究所 | [KuniJiban 利用規約](https://www.kunijiban.pwri.go.jp/jp/terms.html)に基づき複製・頒布 |
| メタデータ | 国土交通データプラットフォーム 国土地盤情報データベース | 国土交通省 | 原則 CC BY 4.0(データ提供者の利活用ルールが優先) |
| 地形 | [Mapterhorn](https://mapterhorn.com/) 全球地形タイル | Mapterhorn | [attribution](https://mapterhorn.com/attribution) |
| 背景地図 | [国土地理院 最適化ベクトルタイル](https://github.com/gsi-cyberjapan/optimal_bvmap)、地理院タイル(写真) | 国土地理院 | [国土地理院コンテンツ利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html) |

## ライセンス

- 本リポジトリのコードは [MIT ライセンス](LICENSE)です。
- サンプル XML は国土地盤情報検索サイト「KuniJiban」の地盤情報です。変換結果を第三者に提供する場合も、KuniJiban の地盤情報であることを表示してください([利用規約](https://www.kunijiban.pwri.go.jp/jp/terms.html) 第 4 条)。
