# 全国のボーリング柱状図データ(${tag})

[boring-data-converter](https://github.com/shiwaku/boring-data-converter) で変換した、全国のボーリング柱状図のデータです。
この版の中身は変更しません。データを更新したときは、新しいタグで別のリリースを出します。

- 柱状図: 国土地盤情報検索サイト「KuniJiban」から ${kunijiban_date} までに取得した XML を変換
- 全国の位置: 国土交通データプラットフォームから ${dpp_date} に取得したメタデータを変換

## ファイル

| ファイル | 中身 | 件数 | 容量 |
| --- | --- | ---: | ---: |
| `kunijiban-borings.parquet` | 孔口(ボーリング 1 本 = 1 行) | ${n_borings} | ${size_0} |
| `kunijiban-layers.parquet` | 土質層(1 層 = 1 行) | ${n_layers} | ${size_1} |
| `kunijiban-spt.parquet` | 標準貫入試験(1 回 = 1 行) | ${n_spt} | ${size_2} |
| `dpp-points.parquet` | 全国のボーリングの位置(XML の無いものも含む) | ${n_dpp} | ${size_3} |
| `japan.mlt.pmtiles` | 柱状図のタイル(孔口・土質層・標準貫入試験) | — | ${size_4} |
| `japan-dpp-points.mlt.pmtiles` | 全国の位置のタイル | — | ${size_5} |
| `SHA256SUMS` | 各ファイルの SHA-256 | — | — |

- Parquet は GeoParquet 1.1(zstd 圧縮)です。ジオメトリはすべて孔口の点(経度・緯度、EPSG:4326)で、土質層・標準貫入試験も孔口の点を持つので、1 ファイルで地図に出せます。
  QGIS、DuckDB(spatial 拡張)、GDAL(Parquet ドライバ)、geopandas などで読めます。
- 3 つの `kunijiban-*.parquet` は `boring_id` でつながります。孔口の `code` と `dpp-points.parquet` の `code` で、全国の位置と突き合わせられます。
- PMTiles は MLT(MapLibre Tile)形式で、MapLibre GL JS で表示できます。タイルには `code`(孔口)と `source_name`(全国の位置)は入っていません。

## 項目

深度・標高はすべて **整数 cm** です。標高は孔口標高から深度を引いた値で、孔口標高が無いボーリングでは null です。

**kunijiban-borings.parquet**

| 項目 | 内容 |
| --- | --- |
| `boring_id` | KuniJiban の ID |
| `code` | KuniJiban のボーリングのコード(例 `B4KJ201801001-2958`、`NGIC202600559-0001`) |
| `name` / `survey_name` / `dtd_version` | ボーリング名、調査名、XML の版 |
| `elevation_cm` / `length_cm` / `water_level_cm` | 孔口標高、総掘進長、孔内水位(孔口からの深さ) |
| `layer_count` / `spt_count` | 土質層の数、標準貫入試験の数 |

**kunijiban-layers.parquet**

| 項目 | 内容 |
| --- | --- |
| `boring_id` | KuniJiban の ID |
| `layer_index` | 上から 0 始まり |
| `top_depth_cm` / `bottom_depth_cm` / `thickness_cm` | 層の上端・下端の深度、層厚 |
| `top_elev_cm` / `bottom_elev_cm` | 層の上端・下端の標高 |
| `soil_name` / `soil_symbol` / `color_name` | 土質名、土質記号、色調 |
| `soil_class` | 土質名の大分類: `topsoil` 表土、`fill` 盛土・埋土、`organic` 有機質土、`volcanic` 火山灰質土(ローム)、`clay` 粘性土、`silt` シルト、`sand` 砂、`gravel` 礫、`rock` 岩、`unknown` 不明。分類の規則は [README](https://github.com/shiwaku/boring-data-converter#土質の大分類soil_class) を参照 |

**kunijiban-spt.parquet**

| 項目 | 内容 |
| --- | --- |
| `boring_id` | KuniJiban の ID |
| `depth_cm` / `elev_cm` | 試験開始深度と標高 |
| `blows` / `penetration_cm` / `n_value` | 合計打撃回数、合計貫入量、30 cm 換算の N 値 |

**dpp-points.parquet**

| 項目 | 内容 |
| --- | --- |
| `dpp_id` / `code` | 国土地盤情報データベースの ID とコード |
| `name` / `survey_name` | ボーリング名、調査名 |
| `elevation_cm` / `length_cm` / `water_level_cm` | 孔口標高、掘進長、孔内水位 |
| `soil_names` | 土質名の一覧(`・` 区切り) |
| `year` / `prefecture` | 年、都道府県 |
| `source_name` | 元データの出どころ。`KuniJiban`、`KuniJiban(港湾)`、自治体(`IB` 茨城県、`ME` 三重県、`SZ` 静岡県、`岐阜県`、`水戸市`)。国土地盤情報センターに登録されたものは null |
| `has_xml` | 国土地盤情報データベースに XML があるか(1 / 0) |

## 柱状図が無い孔

全国の位置(${n_dpp} 件)のうち、約 6 万本は KuniJiban に XML が無く、柱状図(`kunijiban-*`)には入っていません。主に、茨城・三重・静岡・岐阜の自治体のデータ、港湾など XML が無いもの(柱状図は PDF だけ)、国土地盤情報センターにだけあるものです。
詳しくは [#40](https://github.com/shiwaku/boring-data-converter/issues/40) を参照してください。

## 出典と利用条件

このデータには独自のライセンスを付けていません。元データの利用条件に従ってください。第三者に提供するときは、下の出典を表示してください。
リポジトリのコードの MIT ライセンスは、このデータには適用されません。

**柱状図(`kunijiban-*.parquet`、`japan.mlt.pmtiles`)**

- 出典: 国土地盤情報検索サイト「KuniJiban」の地盤情報(国土交通省、国立研究開発法人土木研究所、国立研究開発法人港湾空港技術研究所)
- 利用規約: <https://www.kunijiban.pwri.go.jp/jp/terms.html>
- 規約では、個別のボーリング柱状図などの地盤情報に著作権は無いものとされ、複製・頒布・販売が許諾されています。第三者に提供するときは、国土地盤情報検索サイトの地盤情報であることを表示する必要があります。また、著作権を設定してはいけません

**全国の位置(`dpp-points.parquet`、`japan-dpp-points.mlt.pmtiles`)**

- 出典: 国土交通データプラットフォーム「国土地盤情報データベース」(一般財団法人国土地盤情報センター)のメタデータ
- 国土交通データプラットフォームのデータは原則として CC BY 4.0 で利用できますが、データ提供者が定める利活用ルールが優先されます。データ提供者のルールは、この版を作った時点では確認できていません
- 元データには、KuniJiban の地盤情報と、自治体(茨城県・三重県・静岡県・岐阜県・水戸市など)の地盤情報が含まれます

## 注意

- 元の柱状図の内容をそのまま変換したもので、内容の正しさは保証しません。調査時の座標系の違いなどで、位置がずれている孔があるかもしれません
- 柱状図の XML の内容が後から修正されても、この版には反映されません
