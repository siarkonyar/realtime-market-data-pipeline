import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  TickMarkType,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef } from 'react'
import type { Candle } from '../candles'
import { formatDay, formatDayAndMinute, formatMinute } from '../format'

interface CandleChartProps {
  readonly symbol: string
  readonly candles: readonly Candle[]
}

interface ChartParts {
  readonly chart: IChartApi
  readonly prices: ISeriesApi<'Candlestick'>
  readonly volumes: ISeriesApi<'Histogram'>
  readonly upVolume: string
  readonly downVolume: string
}

// What the chart drew last time. Lets a live tick update one bar instead of
// redrawing the whole day.
interface Drawn {
  readonly symbol: string
  readonly firstTime: number | undefined
  readonly length: number
}

// Three hours of minutes on screen at first; scroll or pinch to see the rest.
const VISIBLE_MINUTES = 180
const RIGHT_MARGIN_BARS = 6

function cssColor(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

// The chart works in UTC; these show each time in the viewer's own zone.
function crosshairLabel(time: Time): string {
  return typeof time === 'number' ? formatDayAndMinute(time) : String(time)
}

function axisLabel(time: Time, type: TickMarkType): string {
  if (typeof time !== 'number') {
    return String(time)
  }
  return type === TickMarkType.Time ? formatMinute(time) : formatDay(time)
}

function createParts(container: HTMLElement): ChartParts {
  const up = cssColor('--up')
  const down = cssColor('--down')
  const grid = cssColor('--grid')

  const chart = createChart(container, {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: cssColor('--text-muted'),
      fontFamily: getComputedStyle(container).fontFamily,
      fontSize: 12,
    },
    grid: { vertLines: { color: grid }, horzLines: { color: grid } },
    crosshair: { mode: CrosshairMode.Normal },
    rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.08, bottom: 0.26 } },
    timeScale: {
      borderVisible: false,
      timeVisible: true,
      secondsVisible: false,
      rightOffset: RIGHT_MARGIN_BARS,
      tickMarkFormatter: axisLabel,
    },
    localization: { timeFormatter: crosshairLabel },
  })

  const prices = chart.addSeries(CandlestickSeries, {
    upColor: up,
    downColor: down,
    borderUpColor: up,
    borderDownColor: down,
    wickUpColor: up,
    wickDownColor: down,
  })

  // Volume sits in the bottom fifth, on its own hidden scale.
  const volumes = chart.addSeries(HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
    lastValueVisible: false,
    priceLineVisible: false,
  })
  chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

  return {
    chart,
    prices,
    volumes,
    upVolume: cssColor('--up-soft'),
    downVolume: cssColor('--down-soft'),
  }
}

function toBar(candle: Candle) {
  return {
    time: candle.time as UTCTimestamp,
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
  }
}

function toVolume(parts: ChartParts, candle: Candle) {
  return {
    time: candle.time as UTCTimestamp,
    value: candle.volume,
    color: candle.close >= candle.open ? parts.upVolume : parts.downVolume,
  }
}

function drawAll(parts: ChartParts, candles: readonly Candle[]): void {
  parts.prices.setData(candles.map(toBar))
  parts.volumes.setData(candles.map((candle) => toVolume(parts, candle)))
}

// Always three hours wide, even with fewer bars: the empty space sits on the
// left, so bars keep one width and new ones arrive on the right.
function showRecent(parts: ChartParts, length: number): void {
  if (length > 0) {
    parts.chart.timeScale().setVisibleLogicalRange({
      from: length - VISIBLE_MINUTES,
      to: length + RIGHT_MARGIN_BARS,
    })
  }
}

// Same symbol, same first minute, and at most one candle more: only the
// newest bar changed (a live tick), so update it and leave the rest alone.
function isLiveTick(drawn: Drawn | null, symbol: string, candles: readonly Candle[]): boolean {
  if (drawn === null || drawn.symbol !== symbol || drawn.firstTime !== candles[0]?.time) {
    return false
  }
  const added = candles.length - drawn.length
  return added === 0 || added === 1
}

function CandleChart({ symbol, candles }: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const partsRef = useRef<ChartParts | null>(null)
  const drawnRef = useRef<Drawn | null>(null)

  // Build the chart once; remove it when the component goes away.
  useEffect(() => {
    const container = containerRef.current
    if (container === null) {
      return
    }
    const parts = createParts(container)
    partsRef.current = parts
    return () => {
      parts.chart.remove()
      partsRef.current = null
      drawnRef.current = null
    }
  }, [])

  useEffect(() => {
    const parts = partsRef.current
    if (parts === null) {
      return
    }

    const drawn = drawnRef.current
    const newest = candles.at(-1)
    if (newest !== undefined && isLiveTick(drawn, symbol, candles)) {
      parts.prices.update(toBar(newest))
      parts.volumes.update(toVolume(parts, newest))
      // While the day is still short (no history, say), every new minute
      // moves the view too, so the newest bar never slides off the right.
      if (drawn !== null && candles.length > drawn.length && candles.length < VISIBLE_MINUTES) {
        showRecent(parts, candles.length)
      }
    } else {
      drawAll(parts, candles)
      if (drawn === null || drawn.symbol !== symbol || drawn.length === 0) {
        showRecent(parts, candles.length)
      }
    }
    drawnRef.current = { symbol, firstTime: candles[0]?.time, length: candles.length }
  }, [symbol, candles])

  return (
    <div className="chart">
      <div className="chart-canvas" ref={containerRef} />
      {candles.length === 0 && (
        <div className="chart-empty">
          <strong>No trades for {symbol} in the last 24 hours</strong>
          <span>The chart fills in by itself as soon as trades come in.</span>
        </div>
      )}
    </div>
  )
}

export default CandleChart
