// Two small candles, one red and one green, drawn inline so no image file is
// needed. Decorative: the text next to it says what it is.
function Logo() {
  return (
    <svg className="logo" viewBox="0 0 32 32" aria-hidden="true">
      <rect className="logo-bg" width="32" height="32" rx="9" />
      <line className="logo-down" x1="11.5" y1="8" x2="11.5" y2="24" />
      <rect className="logo-down" x="8.5" y="12" width="6" height="8" rx="1.5" />
      <line className="logo-up" x1="20.5" y1="6" x2="20.5" y2="22" />
      <rect className="logo-up" x="17.5" y="9" width="6" height="10" rx="1.5" />
    </svg>
  )
}

export default Logo
