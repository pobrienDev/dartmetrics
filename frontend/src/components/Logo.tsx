// Brand mark: a small dartboard glyph next to the wordmark.

import { Link } from 'react-router-dom'

export function BoardGlyph({ className = 'h-7 w-7' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <circle cx="32" cy="32" r="30" className="fill-ink-900" />
      <circle cx="32" cy="32" r="26" className="fill-felt-500" />
      <circle cx="32" cy="32" r="19" className="fill-ink-900" />
      <circle cx="32" cy="32" r="12" className="fill-felt-500" />
      <circle cx="32" cy="32" r="5" className="fill-bust-500" />
    </svg>
  )
}

export function Logo({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2.5" aria-label="DartMetrics home">
      <BoardGlyph />
      <span className="font-display text-2xl font-bold tracking-wide">
        Dart<span className="text-felt-400">Metrics</span>
      </span>
    </Link>
  )
}
