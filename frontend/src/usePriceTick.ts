import { useState } from 'react'
import type { Direction } from './candles'

export interface PriceTick {
  readonly direction: Direction
  // Goes up by one on every price change. Used as a React key, it restarts
  // the flash animation even when the price moves the same way twice.
  readonly count: number
}

interface TickState extends PriceTick {
  readonly price: number | undefined
}

// Which way the price moved last. Worked out while rendering (React's
// "adjust state when a prop changes" pattern), so there is no extra effect.
export function usePriceTick(price: number | undefined): PriceTick {
  const [state, setState] = useState<TickState>({ price, direction: 'flat', count: 0 })

  if (price !== state.price) {
    const before = state.price
    const direction: Direction =
      price === undefined || before === undefined ? 'flat' : price > before ? 'up' : 'down'
    setState({ price, direction, count: state.count + (direction === 'flat' ? 0 : 1) })
  }

  return { direction: state.direction, count: state.count }
}
