import type { CircleLayerSpecification, VectorSourceSpecification } from 'maplibre-gl'

/**
 * 全国のボーリング位置(国土交通データプラットフォームの国土地盤情報データベース)。
 *
 * XML(柱状図の中身)が取れるのは KuniJiban の一部だけなので、位置と孔口標高・掘進長・
 * 土質名の一覧は DPP のメタデータ(26 万件、CC BY 4.0)から出す。タイルは
 * scripts/dpp_points.py → scripts/build_points_tiles.sh で作る。全国分は R2 から配信する。
 */

export const DPP_SOURCE_ID = 'dpp'
export const DPP_LAYER_ID = 'dpp-points'

const DPP_PMTILES_URL = import.meta.env.VITE_DPP_PMTILES_URL
  || new URL(`${import.meta.env.BASE_URL}data/japan-dpp-points.mlt.pmtiles`, location.href).href

export function dppSourceSpec(): VectorSourceSpecification {
  return {
    type: 'vector',
    url: `pmtiles://${DPP_PMTILES_URL}`,
    encoding: 'mlt',
    attribution:
      '<a href="https://www.mlit-data.jp/" target="_blank" rel="noopener">国土交通データプラットフォーム</a>(国土地盤情報データベース)',
  } as VectorSourceSpecification
}

/** 柱状図(円柱)の無い孔も含めた全国の位置。円柱の邪魔をしないよう小さく控えめにする */
export function dppLayer(theme: 'light' | 'dark', visible: boolean): CircleLayerSpecification {
  return {
    id: DPP_LAYER_ID,
    type: 'circle',
    source: DPP_SOURCE_ID,
    'source-layer': 'dpp',
    layout: { visibility: visible ? 'visible' : 'none' },
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 1.5, 10, 2.5, 14, 3.5],
      'circle-color': theme === 'dark' ? '#8fb8ff' : '#2a5db0',
      'circle-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.75, 12, 0.9],
      'circle-stroke-color': theme === 'dark' ? '#14161a' : '#ffffff',
      'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 8, 0, 12, 0.8],
    },
  }
}

const esc = (s: unknown): string =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
const m = (cm: unknown): string => (typeof cm === 'number' ? (cm / 100).toFixed(2) : '–')

export function dppPopupHtml(p: Record<string, unknown>): string {
  const rows = [
    ['調査名', esc(p.survey_name)],
    ['ボーリング名', esc(p.name)],
    ['孔口標高', `T.P. ${m(p.elevation_cm)} m`],
    ['掘進長', `${m(p.length_cm)} m`],
    ['孔内水位', p.water_level_cm != null ? `${m(p.water_level_cm)} m` : '–'],
    ['土質', esc(p.soil_names)],
    // DPF:year は DPP への登録年で、調査年ではない(例: 昭和63年度の調査が 2018)
    ['DPP 登録年', esc(p.year)],
    ['都道府県', esc(p.prefecture)],
  ].filter(([, v]) => v && v !== 'T.P. – m' && v !== '– m')
  return `<div class="pop">
    <div class="pop-head">ボーリング位置(DPP)</div>
    <div class="pop-body">
      <table class="pop-tbl"><tbody>${rows.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join('')}</tbody></table>
      <p class="pop-note">国土地盤情報データベースのメタデータ。柱状図の中身(土質層)は、KuniJiban から XML を取得できた孔だけ円柱で表示している。</p>
    </div>
  </div>`
}
