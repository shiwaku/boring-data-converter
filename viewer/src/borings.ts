import { MapboxOverlay } from '@deck.gl/mapbox'
import { ColumnLayer, ScatterplotLayer, SolidPolygonLayer } from '@deck.gl/layers'
import type { CircleLayerSpecification, Map as MapLibreMap, VectorSourceSpecification } from 'maplibre-gl'

/**
 * ボーリングの土質層を 3D の円柱で表示する。
 *
 * タイルは MLT(boring-convert → tippecanoe → mlt convert)。MLT の仕様は 3D 座標に
 * 対応しているが、MapLibre のデコーダは z を捨てるため、深度・標高は整数 cm の属性で運び、
 * 円柱の高さの組み立ては deck.gl 側で行う(shiwaku/jma-earthquake-data-converter の
 * 震源の立体表示と同じ構成)。
 *
 * タイルの取得は MapLibre の MLT ソースに任せ、読み込まれた地物を querySourceFeatures で
 * 拾って円柱にする。ソースは孔口の点(borings レイヤー)の表示にも使うので取得は 1 系統。
 */

export const SOURCE_ID = 'borings'
export const POINT_LAYER_ID = 'boring-points'
/**
 * 円柱と地表の膜は、この MapLibre レイヤー(全国の位置の点)の手前に差し込む。
 * 孔口の点・地図の注記は膜の上、孔口の輪(deck.gl の最前面)はさらにその上になる。
 */
export const INSERT_BEFORE_ID = 'dpp-points'

export const PMTILES_URL = import.meta.env.VITE_PMTILES_URL
  || new URL(`${import.meta.env.BASE_URL}data/japan.mlt.pmtiles`, location.href).href

export function sourceSpec(): VectorSourceSpecification {
  return {
    type: 'vector',
    url: `pmtiles://${PMTILES_URL}`,
    encoding: 'mlt',
    attribution:
      '<a href="https://www.kunijiban.pwri.go.jp/" target="_blank" rel="noopener">国土地盤情報検索サイト KuniJiban</a>',
  } as VectorSourceSpecification
}

/**
 * 孔口の点。平面で見たときの位置と、タイルを読み込ませるために常に置く。
 * 「地下」表示では deck.gl の輪が孔口を示すので、円が重ならないよう透明にする
 * (visibility: none にするとタイルが読み込まれず円柱も消えるため、不透明度で消す)。
 */
export function pointLayer(theme: 'light' | 'dark', hidden = false): CircleLayerSpecification {
  return {
    id: POINT_LAYER_ID,
    type: 'circle',
    source: SOURCE_ID,
    'source-layer': 'borings',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 1.5, 14, 4],
      'circle-color': theme === 'dark' ? '#f2f4f7' : '#14161a',
      'circle-stroke-color': theme === 'dark' ? '#14161a' : '#ffffff',
      'circle-stroke-width': 1,
      'circle-opacity': hidden ? 0 : 0.8,
      'circle-stroke-opacity': hidden ? 0 : 1,
    },
  }
}

/**
 * 土質の大分類(boring_converter/soil.py の soil_class)と色。
 * 6 色は色覚の違いを含めて全ペアで検証済み。表土・盛土、岩、不明は明度の違う無彩色。
 * 色だけに頼らないよう、層の境目に隙間を空け、クリックで土質名を出す。
 */
export const CLASSES = [
  { codes: ['topsoil', 'fill'], label: '表土・盛土', color: '#a3a3a3' },
  { codes: ['organic'], label: '有機質土', color: '#008300' },
  { codes: ['volcanic'], label: '火山灰質土(ローム)', color: '#e34948' },
  { codes: ['clay'], label: '粘性土', color: '#2a78d6' },
  { codes: ['silt'], label: 'シルト', color: '#1baf7a' },
  { codes: ['sand'], label: '砂', color: '#eda100' },
  { codes: ['gravel'], label: '礫', color: '#4a3aa7' },
  { codes: ['rock'], label: '岩', color: '#4d4d4d' },
  { codes: ['unknown'], label: '不明', color: '#dcdcdc' },
] as const

const CLASS_INDEX: Record<string, number> = {}
CLASSES.forEach((c, i) => c.codes.forEach((code) => { CLASS_INDEX[code] = i }))
const UNKNOWN = CLASS_INDEX.unknown
const RGB = CLASSES.map((c) => [1, 3, 5].map((i) => parseInt(c.color.slice(i, i + 2), 16)) as [number, number, number])

/** 土質層 1 層。タイルの属性をそのまま持つ(深度・標高は cm) */
export interface Layer {
  key: string
  lng: number
  lat: number
  boring_id: string
  layer_index: number
  top_depth_cm: number
  bottom_depth_cm: number
  thickness_cm: number
  top_elev_cm?: number
  bottom_elev_cm?: number
  soil_name?: string
  soil_class: string
  color_name?: string
  cls: number
}

export type HeightMode = 'under' | 'depth'

export interface ViewState {
  mode: HeightMode
  exag: number
  radius: number
  hidden: Set<number>
  /** 3D地形の起伏倍率。地形がオフなら null */
  terrainExag: number | null
  /** 孔口の輪の色をテーマで切り替える */
  theme: 'light' | 'dark'
  /**
   * 「地下に埋める」で地表にかぶせる膜の不透明度(0〜0.8)。濃いほど地下らしく見えるが、
   * 土質の色と背景地図が見えにくくなるので、使う人が選べるようにする
   */
  veil: number
}

/** 層の境目に空ける隙間(表示上の m) */
const GAP_M = 0.4
/**
 * 円柱にする土質層のキャッシュの上限。キャッシュは明滅を防ぐため消さない設計だが、
 * 全国を触っているうちに増え続けるので、超えたら拾った順に古いものから捨てる
 * (jma-earthquake-data-converter の震源の立体表示と同じ方針)。
 */
const MAX_LAYERS = 300_000
/** 当たり判定を広げる(px) */
const PICK_RADIUS = 4

export interface BoringOverlay {
  render(): void
  /** 背景・テーマの切替や地形の切替のあとに地物を拾い直す */
  refresh(): void
  pick(x: number, y: number): Layer | null
  /** 同じボーリングの層(上から順) */
  column(boringId: string): Layer[]
  count(): { borings: number; layers: number }
}

export function createBoringOverlay(map: MapLibreMap, view: ViewState): BoringOverlay {
  const overlay = new MapboxOverlay({ interleaved: true, layers: [] })
  map.addControl(overlay)

  // querySourceFeatures が返す集合はタイルの出入りで変わる。加算キャッシュにして
  // 消さないことで、カメラを動かしたときに円柱が明滅しないようにする。
  const cache = new Map<string, Layer>()
  // 孔ごとの最深部と孔口標高(層の属性から求める)
  const maxDepth = new Map<string, number>()
  const collar = new Map<string, number>()
  // 孔口の位置(「地下」表示で地表の目印の輪を描くため)
  const heads = new Map<string, { id: string; lng: number; lat: number }>()
  let pending = false

  function collect(): void {
    pending = false
    if (!map.getSource(SOURCE_ID)) return
    let added = false
    for (const f of map.querySourceFeatures(SOURCE_ID, { sourceLayer: 'layers' })) {
      const p = f.properties as Record<string, unknown>
      const key = `${p.boring_id}|${p.layer_index}`
      if (cache.has(key) || f.geometry.type !== 'Point') continue
      const [lng, lat] = f.geometry.coordinates as [number, number]
      const d = { ...p, key, lng, lat, boring_id: String(p.boring_id),
        cls: CLASS_INDEX[p.soil_class as string] ?? UNKNOWN } as Layer
      cache.set(key, d)
      maxDepth.set(d.boring_id, Math.max(maxDepth.get(d.boring_id) ?? 0, d.bottom_depth_cm))
      if (d.top_elev_cm != null) collar.set(d.boring_id, d.top_elev_cm + d.top_depth_cm)
      if (!heads.has(d.boring_id)) heads.set(d.boring_id, { id: d.boring_id, lng, lat })
      added = true
    }
    if (!added) return
    if (cache.size > MAX_LAYERS) {
      let over = cache.size - MAX_LAYERS
      for (const key of cache.keys()) {
        cache.delete(key)
        if (--over <= 0) break
      }
    }
    render()
  }

  function schedule(): void {
    if (pending) return
    pending = true
    requestAnimationFrame(collect)
  }

  /** 孔口(地表)の表示高さ [m]。3D地形があれば孔口標高 × 起伏倍率、無ければ 0 */
  function groundZ(boringId: string): number {
    return view.terrainExag != null ? ((collar.get(boringId) ?? 0) / 100) * view.terrainExag : 0
  }

  /** 層の下端の表示高さ [m] */
  function baseZ(d: Layer): number {
    const ground = groundZ(d.boring_id)
    if (view.mode === 'under') {
      // 地下に埋める: 孔口を地面に置き、実際の深さで下へ伸ばす
      return ground - (d.bottom_depth_cm / 100) * view.exag
    }
    // 地上に立てる: 最深部を地面に置いて上に積む。3D地形があれば孔口標高の地面に立てる
    return ground + ((maxDepth.get(d.boring_id)! - d.bottom_depth_cm) / 100) * view.exag
  }

  /**
   * 「地下」表示で地表の位置を示す輪(円柱 1 本に 1 つ)。円柱を地形越しに透かして描くと、
   * 斜めから見たときに地上に立っているように見え、地面との境目が分からなくなるため。
   * 色はテーマで切り替え、淡色地図では濃い色、ダークでは白にする。
   */
  function ringLayers(xray: boolean): ScatterplotLayer[] {
    if (view.mode !== 'under') return []
    const color: [number, number, number, number] = view.theme === 'dark' ? [255, 255, 255, 230] : [20, 22, 26, 220]
    return [
      new ScatterplotLayer<{ id: string; lng: number; lat: number }>({
        id: 'boring-rings',
        data: [...heads.values()],
        // 地形の起伏と孔口標高がずれると輪が地面に埋もれるので、透かし表示のときは深度テストを外す
        parameters: { depthCompare: xray ? 'always' : 'less-equal' },
        getPosition: (h) => [h.lng, h.lat, groundZ(h.id) + 0.5],
        getRadius: view.radius * 1.7,
        filled: false,
        stroked: true,
        billboard: false,
        getLineColor: color,
        lineWidthUnits: 'pixels',
        getLineWidth: 2,
        updateTriggers: { getPosition: [view.terrainExag], getRadius: [view.radius], getLineColor: [view.theme] },
      }),
    ]
  }

  /**
   * 地表の半透明の膜(「地下に埋める」のときだけ)。円柱を描いたあとに画面を覆い、地下の円柱を
   * 膜越しに見せる。地面より手前に描かれていると地上にあるように見える錯覚を減らすため(#4)。
   * MapLibre の fill レイヤーで作ると、3D地形では地形に貼るテクスチャに描かれて円柱との
   * 前後が守られないため、deck.gl で円柱の直後に描く。
   */
  function veilLayers(): SolidPolygonLayer[] {
    if (view.mode !== 'under' || view.veil <= 0) return []
    const alpha = Math.round(view.veil * 255)
    const color: [number, number, number, number] = view.theme === 'dark' ? [20, 22, 26, alpha] : [255, 255, 255, alpha]
    return [
      new SolidPolygonLayer<{ polygon: [number, number][] }>({
        id: 'ground-veil',
        ...({ beforeId: INSERT_BEFORE_ID } as object),
        // 経度 ±180 をまたぐ世界全体の多角形は deck.gl で描かれないため、日本の周りだけを覆う
        data: [{ polygon: [[110, 15], [160, 15], [160, 50], [110, 50]] }],
        getPolygon: (d) => d.polygon,
        getFillColor: color,
        // 奥行きに関係なく上から重ね、深度は書かない(孔口の輪などの判定を邪魔しない)
        parameters: { depthCompare: 'always', depthWriteEnabled: false },
        updateTriggers: { getFillColor: [view.theme, view.veil] },
      }),
    ]
  }

  function render(): void {
    const xray = view.mode === 'under' && view.terrainExag != null
    const data = [...cache.values()].filter((d) => !view.hidden.has(d.cls))
    overlay.setProps({
      layers: [
        new ColumnLayer<Layer>({
          id: 'boring-columns',
          // 全国の位置の点の手前(地表の膜と同じグループ)に差し込む。beforeId は
          // MapboxOverlay(interleaved)が読む設定で、ColumnLayer の型定義には無い
          ...({ beforeId: INSERT_BEFORE_ID } as object),
          data,
          diskResolution: 16,
          radius: view.radius,
          extruded: true,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 150],
          elevationScale: 1,
          // 3D地形は深度を書き込むため、地下の円柱は地面に隠れる。「地下」表示のときだけ
          // 深度テストを外して地形越しに透かして見せる(円柱どうしの前後関係は不正確になる)
          parameters: { depthCompare: xray ? 'always' : 'less-equal' },
          // 透かして見ている(地面の下にある)ことが分かるよう、少し薄くする
          opacity: xray ? 0.7 : 1,
          getPosition: (d) => [d.lng, d.lat, baseZ(d)],
          getElevation: (d) => Math.max((d.thickness_cm / 100) * view.exag - GAP_M, 0.1),
          getFillColor: (d) => RGB[d.cls],
          updateTriggers: {
            getPosition: [view.mode, view.exag, view.terrainExag],
            getElevation: [view.exag],
          },
        }),
        ...veilLayers(),
        ...ringLayers(xray),
      ],
    })
  }

  map.on('sourcedata', (e) => {
    if (e.sourceId === SOURCE_ID && e.sourceDataType !== 'metadata') schedule()
  })
  map.on('moveend', schedule)

  return {
    render,
    refresh: () => map.once('idle', schedule),
    pick(x, y) {
      const info = overlay.pickObject({ x, y, radius: PICK_RADIUS })
      return (info?.object as Layer | undefined) ?? null
    },
    column(boringId) {
      return [...cache.values()].filter((d) => d.boring_id === boringId).sort((a, b) => a.layer_index - b.layer_index)
    },
    count: () => ({ borings: maxDepth.size, layers: cache.size }),
  }
}
