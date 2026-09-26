import type { LayerSpecification, RasterDEMSourceSpecification } from 'maplibre-gl'

/**
 * Mapterhorn の全球地形タイル(terrarium エンコードの標高ラスタ)を
 * 3D地形と陰影起伏に使う。shiwaku/naisui-risk-verification の viewer/src/terrain.ts から
 * 必要な部分(TileJSON 配信・陰影起伏の standard プリセット)だけを抜き出したもの。
 */

export const TILEJSON_URL = 'https://tiles.mapterhorn.com/tilejson.json'

export const MAPTERHORN_ATTRIBUTION =
  '<a href="https://mapterhorn.com/attribution" target="_blank" rel="noopener">© Mapterhorn</a>'

// MapLibre は陰影起伏と3D地形で raster-dem ソースを分けることを推奨している
export const DEM_HILLSHADE = 'dem-hillshade'
export const DEM_TERRAIN = 'dem-terrain'
export const HILLSHADE_ID = 'hillshade'

/** encoding / tileSize は TileJSON 側の記述に従う */
export function demSourceSpec(): RasterDEMSourceSpecification {
  return { type: 'raster-dem', url: TILEJSON_URL, attribution: MAPTERHORN_ATTRIBUTION }
}

export function hillshadeLayer(): LayerSpecification {
  return {
    id: HILLSHADE_ID,
    type: 'hillshade',
    source: DEM_HILLSHADE,
    paint: {
      'hillshade-method': 'standard',
      'hillshade-exaggeration': 0.5,
      'hillshade-shadow-color': '#473B24',
    },
  } as unknown as LayerSpecification
}
