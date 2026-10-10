import type { components } from '../../api/schema'
import { brl, monthLabel } from '../../format'

type History = components['schemas']['HistoryDTO']

export const UNCATEGORIZED_COLOR = 'var(--muted)'

/** Barras empilhadas por mês e categoria; clicar em uma barra seleciona o mês. */
export default function HistoryChart({
  history,
  selected,
  onSelect,
}: {
  history: History
  selected: string
  onSelect: (month: string) => void
}) {
  const colors = new Map<number | null, string>(history.categories.map((c) => [c.id, c.color]))
  const max = Math.max(1, ...history.months.map((m) => m.total_cents))

  return (
    <>
      <div className="history-chart" role="group" aria-label="Histórico mensal de despesas">
        {history.months.map((m) => (
          <button
            type="button"
            key={m.month}
            className="history-bar"
            data-selected={m.month === selected}
            aria-pressed={m.month === selected}
            aria-label={`${monthLabel(m.month)}: ${brl(m.total_cents)}`}
            onClick={() => onSelect(m.month)}
          >
            <span className="history-stack" style={{ height: `${(Math.max(m.total_cents, 0) / max) * 100}%` }}>
              {m.by_category
                .filter((v) => v.total_cents > 0)
                .map((v) => (
                  <span
                    key={v.category_id ?? 'none'}
                    className="history-segment"
                    style={{
                      flexGrow: v.total_cents,
                      background: colors.get(v.category_id) ?? UNCATEGORIZED_COLOR,
                    }}
                  />
                ))}
            </span>
            <span className="history-month">{monthLabel(m.month)}</span>
          </button>
        ))}
      </div>
      <ul className="legend">
        {history.categories.map((c) => (
          <li key={c.id}>
            <span className="swatch" style={{ background: c.color }} /> {c.name}
          </li>
        ))}
        <li>
          <span className="swatch" style={{ background: UNCATEGORIZED_COLOR }} /> Sem categoria
        </li>
      </ul>
    </>
  )
}
