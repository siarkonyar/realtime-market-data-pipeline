import { finiteNumber, isRecord, isString } from './guards'

// One minute of trading for one symbol. time is the minute's start in UTC
// seconds, the unit the chart wants.
export interface Candle {
  readonly symbol: string
  readonly time: number
  readonly open: number
  readonly high: number
  readonly low: number
  readonly close: number
  readonly volume: number
}

export type Direction = 'up' | 'down' | 'flat'

export interface Summary {
  readonly last: number
  readonly open: number
  readonly change: number
  readonly changeRatio: number
  readonly high: number
  readonly low: number
  readonly volume: number
  readonly direction: Direction
}

// 24 hours of minutes, plus room for the live ones that arrive afterwards.
const MAX_CANDLES = 24 * 60 + 120

// The api writes "2026-11-15T14:31:00+00:00". A minute with no offset is UTC
// too; without the Z the browser would read it as local time.
const HAS_OFFSET = /([zZ]|[+-]\d{2}:\d{2})$/

function minuteToSeconds(minute: string): number {
  return Date.parse(HAS_OFFSET.test(minute) ? minute : `${minute}Z`) / 1000
}

// Used for both GET /candles and /ws/candles. Anything that is not a whole
// candle becomes null, instead of a chart full of NaN.
export function parseCandle(value: unknown): Candle | null {
  if (!isRecord(value) || !isString(value.symbol) || !isString(value.minute)) {
    return null
  }

  const time = minuteToSeconds(value.minute)
  const open = finiteNumber(value.open)
  const high = finiteNumber(value.high)
  const low = finiteNumber(value.low)
  const close = finiteNumber(value.close)
  const volume = finiteNumber(value.volume)

  if (
    !Number.isFinite(time) ||
    open === null ||
    high === null ||
    low === null ||
    close === null ||
    volume === null
  ) {
    return null
  }

  return { symbol: value.symbol, time, open, high, low, close, volume }
}

// Replace-or-add by minute. The current minute's candle arrives many times
// as trades come in (replace); the first trade of a new minute adds one.
export function mergeCandle(candles: readonly Candle[], candle: Candle): readonly Candle[] {
  const last = candles.at(-1)
  if (last === undefined || candle.time > last.time) {
    return [...candles, candle].slice(-MAX_CANDLES)
  }

  const index = candles.findIndex((existing) => existing.time === candle.time)
  if (index === -1) {
    return candles
  }
  return candles.map((existing, position) => (position === index ? candle : existing))
}

// History can arrive after the first live candles; those go on top of it.
export function mergeHistory(
  history: readonly Candle[],
  live: readonly Candle[],
): readonly Candle[] {
  return live.reduce(mergeCandle, history.slice(-MAX_CANDLES))
}

export function directionOf(change: number): Direction {
  if (change > 0) {
    return 'up'
  }
  return change < 0 ? 'down' : 'flat'
}

// The numbers above the chart, over everything loaded (up to 24 hours).
export function summarize(candles: readonly Candle[]): Summary | null {
  const first = candles[0]
  const last = candles.at(-1)
  if (first === undefined || last === undefined) {
    return null
  }

  const change = last.close - first.open
  return {
    last: last.close,
    open: first.open,
    change,
    changeRatio: first.open === 0 ? 0 : change / first.open,
    high: Math.max(...candles.map((candle) => candle.high)),
    low: Math.min(...candles.map((candle) => candle.low)),
    volume: candles.reduce((total, candle) => total + candle.volume, 0),
    direction: directionOf(change),
  }
}
