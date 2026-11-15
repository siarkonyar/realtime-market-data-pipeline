// Built once: creating an Intl formatter on every render is slow.
const priceFormat = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const changeFormat = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
})

const percentFormat = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
})

const volumeFormat = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

// undefined: the viewer's own locale and time zone.
const clockFormat = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

const minuteFormat = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
})

const dayFormat = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
})

const dayAndMinuteFormat = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatPrice(price: number): string {
  return priceFormat.format(price)
}

export function formatChange(change: number): string {
  return changeFormat.format(change)
}

// ratio 0.0123 -> "+1.23%"
export function formatPercent(ratio: number): string {
  return percentFormat.format(ratio)
}

export function formatVolume(volume: number): string {
  return volumeFormat.format(volume)
}

export function formatClock(milliseconds: number): string {
  return clockFormat.format(milliseconds)
}

export function formatMinute(seconds: number): string {
  return minuteFormat.format(seconds * 1000)
}

export function formatDay(seconds: number): string {
  return dayFormat.format(seconds * 1000)
}

export function formatDayAndMinute(seconds: number): string {
  return dayAndMinuteFormat.format(seconds * 1000)
}
