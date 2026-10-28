import { useT } from '../i18n'
import { colorAt } from '../lib/palette'

export interface Segment {
  name: string
  share: string // percent as a decimal string from the backend, e.g. "31.67"
}

const RADIUS = 70
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const GAP = 2

interface Props {
  segments: Segment[]
  centerLabel: string
  centerValue: string
}

// Ring chart drawn as SVG strokes, as in the mockups. Shares are geometry here, not money.
export function Donut({ segments, centerLabel, centerValue }: Props) {
  const t = useT()
  const arcs = segments.map((segment, index) => {
    const before = segments
      .slice(0, index)
      .reduce((sum, item) => sum + (CIRCUMFERENCE * Number(item.share)) / 100, 0)
    const length = Math.max(0, (CIRCUMFERENCE * Number(segment.share)) / 100 - GAP)
    return { color: colorAt(index), length, offset: before }
  })
  const description = segments.map((s) => `${s.name} ${s.share}%`).join(', ')

  return (
    <div className="relative size-[200px] shrink-0">
      <svg
        width="200"
        height="200"
        viewBox="0 0 200 200"
        role="img"
        aria-label={segments.length ? t.overview.donutAria(description) : t.overview.donutEmpty}
      >
        <g transform="rotate(-90 100 100)" fill="none" strokeWidth="26">
          {segments.length === 0 && <circle cx="100" cy="100" r={RADIUS} stroke="var(--line)" />}
          {arcs.map((arc, i) => (
            <circle
              key={i}
              cx="100"
              cy="100"
              r={RADIUS}
              stroke={arc.color}
              strokeDasharray={`${arc.length} ${CIRCUMFERENCE - arc.length}`}
              strokeDashoffset={-arc.offset}
            />
          ))}
        </g>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden="true">
        <span className="text-[13px] text-muted">{centerLabel}</span>
        <span className="text-[26px] font-light">{centerValue}</span>
      </div>
    </div>
  )
}
