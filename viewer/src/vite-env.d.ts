/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 土質層 PMTiles(MLT)の配信先を差し替える(既定は data/tokyo23.mlt.pmtiles) */
  readonly VITE_PMTILES_URL?: string
}

/** vite.config.ts の define で埋め込むビルド時刻 */
declare const __BUILD_TIME__: string
