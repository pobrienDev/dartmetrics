// Decorative dartboard for the auth pages. Twenty wedges, double and
// triple rings, and the bull, drawn with SVG arcs. Purely visual.

const SEGMENTS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

function wedge(index: number, inner: number, outer: number): string {
  const step = (Math.PI * 2) / 20
  const start = -Math.PI / 2 - step / 2 + index * step
  const end = start + step
  const p = (r: number, a: number) => `${(100 + r * Math.cos(a)).toFixed(2)} ${(100 + r * Math.sin(a)).toFixed(2)}`
  return [
    `M ${p(inner, start)}`,
    `L ${p(outer, start)}`,
    `A ${outer} ${outer} 0 0 1 ${p(outer, end)}`,
    `L ${p(inner, end)}`,
    `A ${inner} ${inner} 0 0 0 ${p(inner, start)}`,
    'Z',
  ].join(' ')
}

export function Dartboard({ className = 'h-72 w-72' }: { className?: string }) {
  const rings: [number, number, (i: number) => string][] = [
    [88, 96, (i) => (i % 2 === 0 ? 'fill-bust-500' : 'fill-felt-500')], // double
    [58, 88, (i) => (i % 2 === 0 ? 'fill-ink-900' : 'fill-ink-100')], // outer single
    [52, 58, (i) => (i % 2 === 0 ? 'fill-bust-500' : 'fill-felt-500')], // triple
    [16, 52, (i) => (i % 2 === 0 ? 'fill-ink-900' : 'fill-ink-100')], // inner single
  ]
  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden="true">
      <circle cx="100" cy="100" r="100" className="fill-ink-950" />
      {rings.map(([inner, outer, fill]) =>
        SEGMENTS.map((_, i) => (
          <path key={`${inner}-${i}`} d={wedge(i, inner, outer)} className={fill(i)} />
        )),
      )}
      <circle cx="100" cy="100" r="16" className="fill-felt-500" />
      <circle cx="100" cy="100" r="7" className="fill-bust-500" />
      {SEGMENTS.map((n, i) => {
        const a = -Math.PI / 2 + i * ((Math.PI * 2) / 20)
        return (
          <text
            key={n}
            x={100 + 108 * Math.cos(a)}
            y={100 + 108 * Math.sin(a)}
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-ink-300 font-display text-[10px] font-bold"
          >
            {n}
          </text>
        )
      })}
    </svg>
  )
}
