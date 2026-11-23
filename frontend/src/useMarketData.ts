import { useEffect, useEffectEvent, useReducer, useState } from 'react'
import { ApiError, fetchCandles, fetchSymbols } from './api'
import { mergeCandle, mergeHistory, type Candle } from './candles'
import { isAbortError } from './guards'
import { openLiveCandles, type LiveStatus } from './liveSocket'

export interface SymbolState {
  readonly candles: readonly Candle[]
  readonly status: LiveStatus
  // When the last live candle arrived (ms), or null before the first one.
  readonly lastTickAt: number | null
}

export type MarketState = Readonly<Record<string, SymbolState>>

type Action =
  | { readonly type: 'history'; readonly symbol: string; readonly candles: readonly Candle[] }
  | { readonly type: 'candle'; readonly symbol: string; readonly candle: Candle; readonly receivedAt: number }
  | { readonly type: 'status'; readonly symbol: string; readonly status: LiveStatus }

export const EMPTY_SYMBOL: SymbolState = { candles: [], status: 'connecting', lastTickAt: null }

// Every change makes a new state object, so React sees exactly what changed.
function reducer(state: MarketState, action: Action): MarketState {
  const current = state[action.symbol] ?? EMPTY_SYMBOL

  switch (action.type) {
    case 'history':
      return {
        ...state,
        [action.symbol]: { ...current, candles: mergeHistory(action.candles, current.candles) },
      }
    case 'candle':
      return {
        ...state,
        [action.symbol]: {
          ...current,
          candles: mergeCandle(current.candles, action.candle),
          lastTickAt: action.receivedAt,
        },
      }
    case 'status':
      return { ...state, [action.symbol]: { ...current, status: action.status } }
  }
}

export interface MarketData {
  readonly symbols: readonly string[]
  readonly market: MarketState
  readonly error: string | null
}

// The followed symbols, 24 hours of history for each, and one WebSocket per
// symbol that keeps the newest candle live.
export function useMarketData(onUnauthorized: () => void): MarketData {
  const [symbols, setSymbols] = useState<readonly string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [market, dispatch] = useReducer(reducer, {})

  // Effect events always see the latest props, without being dependencies:
  // a new onUnauthorized from the parent must not reopen every socket.
  const handleUnauthorized = useEffectEvent(onUnauthorized)
  const handleFailure = useEffectEvent((caught: unknown) => {
    if (isAbortError(caught)) {
      return
    }
    if (caught instanceof ApiError && caught.status === 401) {
      onUnauthorized()
      return
    }
    setError(caught instanceof Error ? caught.message : 'Something went wrong.')
  })

  useEffect(() => {
    const controller = new AbortController()
    fetchSymbols(controller.signal).then(setSymbols, (caught) => handleFailure(caught))
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    for (const symbol of symbols) {
      fetchCandles(symbol, controller.signal).then(
        (candles) => dispatch({ type: 'history', symbol, candles }),
        (caught) => handleFailure(caught),
      )
    }
    return () => controller.abort()
  }, [symbols])

  useEffect(() => {
    const stops = symbols.map((symbol) =>
      openLiveCandles(symbol, {
        onCandle: (candle) =>
          dispatch({ type: 'candle', symbol, candle, receivedAt: Date.now() }),
        onStatus: (status) => {
          dispatch({ type: 'status', symbol, status })
          if (status === 'unauthorized') {
            handleUnauthorized()
          }
        },
      }),
    )
    return () => {
      for (const stop of stops) {
        stop()
      }
    }
  }, [symbols])

  return { symbols, market, error }
}
