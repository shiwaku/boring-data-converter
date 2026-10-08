import { CLASSES, type Layer, type Spt } from './borings'

/**
 * ポップアップに出す簡易の柱状図(土質の帯と N 値のグラフ)。
 * 紙の柱状図と同じく深度を下向きに取り、左に土質、右に N 値を並べる。
 */

/** N 値のグラフの右端。これを超える値は右端に寄せて ▶ で示す */
const N_MAX = 50
/** 支持層の目安: N 値 50 以上がこの厚さ [cm] 続く最初の深度 */
const SUPPORT_CM = 500

/**
 * 支持層の目安の深度 [cm]。その深度から 5 m 先までの試験がすべて N 値 50 以上で、
 * 5 m 先の近くまで試験がある(掘り止めで途切れていない)最初の試験の深度。
 * 設計で使う支持層の判定(土質・地域の基準による)とは別物で、あくまで目安。
 */
export function supportDepthCm(spts: Spt[]): number | null {
  for (const s of spts) {
    const win = spts.filter((t) => t.depth_cm >= s.depth_cm && t.depth_cm <= s.depth_cm + SUPPORT_CM)
    if (win.every((t) => (t.n_value ?? -1) >= 50) && win[win.length - 1].depth_cm >= s.depth_cm + SUPPORT_CM - 100) {
      return s.depth_cm
    }
  }
  return null
}

/** 層の範囲に入る試験の N 値を「最小〜最大」で返す。試験が無ければ空文字 */
export function nRange(layer: Layer, spts: Spt[]): string {
  const ns = spts
    .filter((s) => s.depth_cm >= layer.top_depth_cm && s.depth_cm < layer.bottom_depth_cm && s.n_value != null)
    .map((s) => s.n_value!)
  if (!ns.length) return ''
  const lo = Math.min(...ns)
  const hi = Math.max(...ns)
  return lo === hi ? String(lo) : `${lo}〜${hi}`
}

/** 目盛りの間隔 [m]。最深部に応じて 5 本前後になるようにする */
function tickStep(maxM: number): number {
  return [1, 2, 5, 10, 20, 50].find((s) => maxM / s <= 6) ?? 100
}

export function logSvg(layers: Layer[], spts: Spt[], waterCm: number | undefined, supportCm: number | null): string {
  const maxCm = Math.max(
    ...layers.map((d) => d.bottom_depth_cm),
    ...spts.map((s) => s.depth_cm + 30),
    1,
  )
  const W = 300
  const H = 240
  const top = 16
  const bottom = 6
  const axisX = 30
  const bandX = axisX + 4
  const bandW = 22
  const plotX = bandX + bandW + 14
  const plotW = W - plotX - 14
  const y = (cm: number): number => top + (cm / maxCm) * (H - top - bottom)
  const x = (n: number): number => plotX + (Math.min(n, N_MAX) / N_MAX) * plotW
  const out: string[] = []

  // 深度の目盛り
  const step = tickStep(maxCm / 100)
  for (let m = 0; m * 100 <= maxCm; m += step) {
    const yy = y(m * 100)
    out.push(`<line class="lg-grid" x1="${bandX}" x2="${plotX + plotW}" y1="${yy}" y2="${yy}"/>`)
    out.push(`<text class="lg-tick" x="${axisX - 2}" y="${yy + 3}" text-anchor="end">${m}</text>`)
  }
  out.push(`<text class="lg-tick" x="${axisX - 2}" y="${top - 6}" text-anchor="end">m</text>`)

  // N 値の目盛り
  for (let n = 0; n <= N_MAX; n += 10) {
    out.push(`<line class="lg-grid" x1="${x(n)}" x2="${x(n)}" y1="${top}" y2="${H - bottom}"/>`)
    out.push(`<text class="lg-tick" x="${x(n)}" y="${top - 6}" text-anchor="middle">${n}</text>`)
  }
  out.push(`<text class="lg-tick" x="${plotX + plotW + 4}" y="${top - 6}">N</text>`)

  // 土質の帯
  for (const d of layers) {
    const c = CLASSES[d.cls]
    const h = Math.max(y(d.bottom_depth_cm) - y(d.top_depth_cm), 0.5)
    out.push(`<rect x="${bandX}" y="${y(d.top_depth_cm)}" width="${bandW}" height="${h}" fill="${c.color}"><title>${c.label}</title></rect>`)
  }
  out.push(`<rect class="lg-frame" x="${bandX}" y="${top}" width="${bandW}" height="${H - top - bottom}"/>`)

  // 支持層の目安と孔内水位
  if (supportCm != null) {
    const yy = y(supportCm)
    out.push(`<line class="lg-support" x1="${bandX}" x2="${plotX + plotW}" y1="${yy}" y2="${yy}"/>`)
  }
  if (waterCm != null && waterCm <= maxCm) {
    const yy = y(waterCm)
    out.push(`<line class="lg-water" x1="${bandX - 4}" x2="${bandX + bandW + 4}" y1="${yy}" y2="${yy}"/>`)
    out.push(`<path class="lg-water-mark" d="M${bandX + bandW + 6},${yy - 7} h8 l-4,6 z"/>`)
  }

  // N 値(試験区間の中央に打つ)
  const pts = spts.filter((s) => s.n_value != null).map((s) => ({ s, px: x(s.n_value!), py: y(s.depth_cm + 15) }))
  if (pts.length > 1) out.push(`<polyline class="lg-n-line" points="${pts.map((p) => `${p.px},${p.py}`).join(' ')}"/>`)
  for (const { s, px, py } of pts) {
    const tip = `${(s.depth_cm / 100).toFixed(2)} m: N=${s.n_value}`
    out.push(s.n_value! > N_MAX
      ? `<path class="lg-n-over" d="M${px - 4},${py - 4} l6,4 l-6,4 z"><title>${tip}</title></path>`
      : `<circle class="lg-n-dot" cx="${px}" cy="${py}" r="2.5"><title>${tip}</title></circle>`)
  }

  return `<svg class="lg" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="土質と N 値の柱状図">${out.join('')}</svg>`
}
