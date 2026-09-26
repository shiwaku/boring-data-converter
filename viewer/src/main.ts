import * as maplibregl from 'maplibre-gl'
// maplibre 6 はワーカーの場所を実行時に import.meta.url から決める。バンドルすると
// import.meta.url が assets/index-*.js を指してワーカーが 404 になり、タイルが 1 枚も
// 復号されない。?worker&url で別チャンクに吐かせて、その URL を渡す
// (shiwaku/jma-earthquake-data-converter の viewer と同じ対処)。
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'

import { BASEMAPS, getBasemapStyle, type Basemap } from './basemap'
import {
  CLASSES,
  ELEV_OFFSET_M,
  POINT_LAYER_ID,
  SOURCE_ID,
  createBoringOverlay,
  pointLayer,
  sourceSpec,
  type HeightMode,
  type Layer,
  type ViewState,
} from './borings'
import { DEM_HILLSHADE, DEM_TERRAIN, HILLSHADE_ID, demSourceSpec, hillshadeLayer } from './terrain'
import { applyThemeAttr, initialTheme, type Theme } from './theme'
import './style.css'

maplibregl.setWorkerUrl(workerUrl)

// ---- 状態 ----

let theme: Theme = initialTheme()
let base: Basemap = 'pale'
applyThemeAttr(theme)

// 陰影起伏と3D地形は最初からオンにする(地形と柱状図の関係を見るビューワなので)
let hillshadeOn = true
let terrainOn = true
let terrainExag = 1

const view: ViewState = { mode: 'under', exag: 5, radius: 12, hidden: new Set(), terrainExag: 1 }

const isMobile = window.matchMedia('(max-width: 640px)').matches

// ---- 地図 ----

const protocol = new Protocol()
maplibregl.addProtocol('pmtiles', protocol.tile)

const map = new maplibregl.Map({
  container: 'map',
  style: await getBasemapStyle(base, theme),
  center: [139.72, 35.68],
  zoom: 12,
  pitch: 60,
  bearing: -20,
  // 柱状図は深さ方向が主役なので、断面のように横から見られるよう上限を上げる
  maxPitch: 85,
  hash: true,
  attributionControl: false,
  maxTileCacheSize: isMobile ? 24 : undefined,
  pixelRatio: isMobile ? Math.min(window.devicePixelRatio || 1, 2) : undefined,
})

/**
 * deck.gl(@deck.gl/mapbox)との互換のため map.transform を生やす。
 * maplibre 6 で transform が map._camera.transform へ移り、deck.gl の interleaved 描画が
 * 「Cannot read properties of undefined (reading 'height')」で落ちるため
 * (shiwaku/jma-earthquake-data-converter の viewer/src/map/createMap.ts と同じ対処)。
 */
{
  const m = map as unknown as { transform?: unknown; _camera?: { transform?: unknown } }
  if (!m.transform && m._camera?.transform) {
    Object.defineProperty(map, 'transform', {
      get: () => (map as unknown as { _camera: { transform: unknown } })._camera.transform,
      configurable: true,
    })
  }
}

map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), 'top-right')
map.addControl(new maplibregl.FullscreenControl(), 'top-right')
map.addControl(new maplibregl.ScaleControl({ maxWidth: 200, unit: 'metric' }), 'bottom-left')
map.addControl(new maplibregl.AttributionControl({ compact: true }))

const borings = createBoringOverlay(map, view)

// ---- 自前のレイヤー ----

function removeLayer(id: string): void {
  if (map.getLayer(id)) map.removeLayer(id)
}
function removeSource(id: string): void {
  if (map.getSource(id)) map.removeSource(id)
}
function whenStyleReady(fn: () => void): void {
  if (map.isStyleLoaded()) fn()
  else map.once('idle', fn)
}

/** 背景地図の注記(source-layer = Anno)。自前の平面レイヤーはこの手前に差し込む */
function labelBeforeId(): string | undefined {
  const layers = map.getStyle()?.layers ?? []
  return layers.find((l) => (l as { 'source-layer'?: string })['source-layer'] === 'Anno')?.id
}

function applyHillshade(): void {
  whenStyleReady(() => {
    removeLayer(HILLSHADE_ID)
    if (!hillshadeOn) {
      removeSource(DEM_HILLSHADE)
      return
    }
    if (!map.getSource(DEM_HILLSHADE)) map.addSource(DEM_HILLSHADE, demSourceSpec())
    map.addLayer(hillshadeLayer(), map.getLayer(POINT_LAYER_ID) ? POINT_LAYER_ID : labelBeforeId())
  })
}

function applyTerrain(): void {
  view.terrainExag = terrainOn ? terrainExag : null
  whenStyleReady(() => {
    if (terrainOn) {
      if (!map.getSource(DEM_TERRAIN)) map.addSource(DEM_TERRAIN, demSourceSpec())
      map.setTerrain({ source: DEM_TERRAIN, exaggeration: terrainExag })
      // 視線を倒すと地平線の先が見える。sky を出さないとそこが背景色のままになる
      map.setSky({})
    } else {
      map.setTerrain(null)
      requestAnimationFrame(() => {
        if (!terrainOn) removeSource(DEM_TERRAIN)
      })
    }
    borings.render()
  })
}

function applyBorings(): void {
  whenStyleReady(() => {
    removeLayer(POINT_LAYER_ID)
    if (!map.getSource(SOURCE_ID)) map.addSource(SOURCE_ID, sourceSpec())
    map.addLayer(pointLayer(theme), labelBeforeId())
    borings.refresh()
  })
}

function applyLayers(): void {
  applyBorings()
  applyHillshade()
  applyTerrain()
}

// ラスタ(写真)↔ベクタ(標準地図)の切替では diff が効かないため diff:false で作り直し、
// 新スタイルが落ち着く idle を待ってから自前のレイヤーを貼り直す
async function reloadStyle(): Promise<void> {
  map.setStyle(await getBasemapStyle(base, theme), { diff: false })
  map.once('idle', applyLayers)
}

// ---- ヘッダのボタン ----

const el = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T

const themeBtn = el<HTMLButtonElement>('theme-btn')
const renderThemeBtn = (): void => {
  themeBtn.textContent = theme === 'dark' ? '☀️' : '🌙'
}
themeBtn.addEventListener('click', () => {
  theme = theme === 'dark' ? 'light' : 'dark'
  applyThemeAttr(theme)
  renderThemeBtn()
  void reloadStyle()
})

const panel = el('panel')
const collapseBtn = el<HTMLButtonElement>('collapse-btn')
const renderCollapseBtn = (): void => {
  collapseBtn.textContent = panel.classList.contains('collapsed') ? '▾' : '▴'
}
collapseBtn.addEventListener('click', () => {
  panel.classList.toggle('collapsed')
  renderCollapseBtn()
})

// ---- 柱状図 ----

const HEIGHT_MODES: { key: HeightMode; label: string; note: string }[] = [
  {
    key: 'under',
    label: '地下',
    note: '孔口を地面に置き、実際の深さのとおり地下へ伸ばす。地図を透かして見る表示で、前後関係は正確でない。',
  },
  {
    key: 'elev',
    label: '標高で比較',
    note: `T.P.(東京湾平均海面)で高さをそろえる。孔どうしで同じ地層の高さを見比べられる。T.P. −${ELEV_OFFSET_M} m を地面の高さにしている。`,
  },
  {
    key: 'depth',
    label: '地上に立てる',
    note: '各孔の最深部を地面に置き、地表を上にして積む。孔口標高の無い孔も表示できる。',
  },
]
const heightModesEl = el('height-modes')
const heightNoteEl = el('height-note')
function renderHeightModes(): void {
  heightModesEl.replaceChildren(
    ...HEIGHT_MODES.map(({ key, label }) => {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.textContent = label
      btn.setAttribute('aria-pressed', String(key === view.mode))
      btn.addEventListener('click', () => {
        if (view.mode === key) return
        view.mode = key
        renderHeightModes()
        borings.render()
      })
      return btn
    }),
  )
  heightNoteEl.textContent = HEIGHT_MODES.find((m) => m.key === view.mode)!.note
}

function slider(id: string, fmt: (v: number) => string, onInput: (v: number) => void): void {
  const input = el<HTMLInputElement>(id)
  const val = el(`${id}-val`)
  input.addEventListener('input', () => {
    const v = Number(input.value)
    val.textContent = fmt(v)
    onInput(v)
  })
}
slider('exag', (v) => `${v}倍`, (v) => { view.exag = v; borings.render() })
slider('radius', (v) => `${v}m`, (v) => { view.radius = v; borings.render() })

// ---- 凡例(クリックで表示切替) ----

const legendEl = el<HTMLUListElement>('legend')
function renderLegend(): void {
  legendEl.replaceChildren(
    ...CLASSES.map((c, i) => {
      const li = document.createElement('li')
      li.tabIndex = 0
      li.setAttribute('role', 'switch')
      li.setAttribute('aria-checked', String(!view.hidden.has(i)))
      const sw = document.createElement('span')
      sw.className = 'sw'
      sw.style.background = c.color
      const label = document.createElement('span')
      label.className = 'lg-label'
      label.textContent = c.label
      li.append(sw, label)
      const toggle = (): void => {
        if (view.hidden.has(i)) view.hidden.delete(i)
        else view.hidden.add(i)
        renderLegend()
        borings.render()
      }
      li.addEventListener('click', toggle)
      li.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle() }
      })
      return li
    }),
  )
}

// ---- 地形 ----

const hillshadeOnEl = el<HTMLInputElement>('hillshade-on')
hillshadeOnEl.addEventListener('change', () => { hillshadeOn = hillshadeOnEl.checked; applyHillshade() })

const terrainOnEl = el<HTMLInputElement>('terrain-on')
const terrainOptsEl = el('terrain-opts')
terrainOnEl.addEventListener('change', () => {
  terrainOn = terrainOnEl.checked
  terrainOptsEl.hidden = !terrainOn
  applyTerrain()
})
slider('terrain-exag', (v) => v.toFixed(1), (v) => {
  terrainExag = v
  view.terrainExag = terrainOn ? v : null
  if (terrainOn) map.setTerrain({ source: DEM_TERRAIN, exaggeration: v })
  borings.render()
})

// ---- 背景地図スイッチャー(右下) ----

class BasemapControl implements maplibregl.IControl {
  private el!: HTMLElement
  onAdd(): HTMLElement {
    this.el = document.createElement('div')
    this.el.className = 'maplibregl-ctrl basemap-switch'
    for (const { key, label } of BASEMAPS) {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.textContent = label
      btn.dataset.base = key
      btn.setAttribute('aria-selected', String(key === base))
      btn.addEventListener('click', () => setBase(key))
      this.el.append(btn)
    }
    return this.el
  }
  onRemove(): void {
    this.el.remove()
  }
  sync(): void {
    for (const btn of this.el.querySelectorAll<HTMLButtonElement>('button')) {
      btn.setAttribute('aria-selected', String(btn.dataset.base === base))
    }
  }
}
const basemapCtrl = new BasemapControl()
map.addControl(basemapCtrl, 'bottom-right')

function setBase(next: Basemap): void {
  if (next === base) return
  base = next
  basemapCtrl.sync()
  void reloadStyle()
}

// ---- クリックでその孔の全層を表示 ----

const esc = (s: unknown): string =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
const m = (cm: number | undefined): string => (cm == null ? '–' : (cm / 100).toFixed(2))

function popupHtml(hit: Layer): string {
  const rows = borings.column(hit.boring_id).map((d) => {
    const c = CLASSES.find((_, i) => i === d.cls)!
    const cur = d.key === hit.key ? ' class="pop-cur"' : ''
    return `<tr${cur}><td>${m(d.top_depth_cm)}〜${m(d.bottom_depth_cm)}</td>` +
      `<td><span class="sw" style="background:${c.color}"></span>${esc(d.soil_name ?? '(土質名なし)')}</td></tr>`
  })
  const collarCm = hit.top_elev_cm != null ? hit.top_elev_cm + hit.top_depth_cm : undefined
  const pdf = `https://www.kunijiban.pwri.go.jp/viewer/refer/?data=boring&type=view&id=${encodeURIComponent(hit.boring_id)}`
  return `<div class="pop">
    <div class="pop-head">ボーリング ${esc(hit.boring_id)}</div>
    <div class="pop-body">
      <p class="pop-note">孔口標高 T.P. ${m(collarCm)} m</p>
      <table class="pop-tbl pop-column"><thead><tr><th>深度 (m)</th><th>土質</th></tr></thead><tbody>${rows.join('')}</tbody></table>
    </div>
    <div class="pop-foot"><a href="${pdf}" target="_blank" rel="noopener">柱状図(PDF)を KuniJiban で開く</a></div>
  </div>`
}

const popup = new maplibregl.Popup({ closeButton: true, maxWidth: '340px' })
map.on('click', (e) => {
  const hit = borings.pick(e.point.x, e.point.y)
  if (!hit) return
  popup.setLngLat([hit.lng, hit.lat]).setHTML(popupHtml(hit)).addTo(map)
})
if (window.matchMedia('(hover: hover)').matches) {
  map.on('mousemove', (e) => {
    map.getCanvas().style.cursor = borings.pick(e.point.x, e.point.y) ? 'pointer' : ''
  })
}

// 読み込み済みの件数(読み込んだタイルの分だけ)
map.on('idle', () => {
  const c = borings.count()
  el('feature-count').textContent = c.borings ? `${c.borings.toLocaleString('ja-JP')}本` : '–'
})

// ---- 初期化 ----

hillshadeOnEl.checked = hillshadeOn
terrainOnEl.checked = terrainOn
terrainOptsEl.hidden = !terrainOn
renderThemeBtn()
renderHeightModes()
renderLegend()
el('build-ver').textContent = `build ${__BUILD_TIME__}`
if (isMobile) panel.classList.add('collapsed')
renderCollapseBtn()
map.on('load', applyLayers)

// デバッグ用
;(window as unknown as { __map: maplibregl.Map }).__map = map
