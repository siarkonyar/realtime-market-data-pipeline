import { useMemo } from 'react'
import type { Candle, Direction } from '../candles'

interface SparklineProps {
  readonly candles: readonly Candle[]
  readonly direction: Direction
}

const WIDTH = 100
const HEIGHT = 30
// A day has up to 1440 minutes; 60 points draw the same shape.
const MAX_POINTS = 60

function linePoints(candles: readonly Candle[]): string {
  if (candles.length < 2) {
    return ''
  }

  const step = Math.ceil(candles.length / MAX_POINTS)
  const closes = candles
    .filter((_, index) => index % step === 0 || index === candles.length - 1)
    .map((candle) => candle.close)
  const low = Math.min(...closes)
  const range = Math.max(...closes) - low || 1

  return closes
    .map((close, index) => {
      const x = (index / (closes.length - 1)) * WIDTH
      const y = HEIGHT - 2 - ((close - low) / range) * (HEIGHT - 4)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

// The day's closes as a tiny line, green or red by the day's change.
function Sparkline({ candles, direction }: SparklineProps) {
  const points = useMemo(() => linePoints(candles), [candles])

  return (
    <svg
      className={`sparkline sparkline-${direction}`}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {points === '' ? (
        <line x1="0" y1={HEIGHT / 2} x2={WIDTH} y2={HEIGHT / 2} strokeDasharray="3 4" />
      ) : (
        <polyline points={points} />
      )}
    </svg>
  )
}

export default Sparkline
