import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorDetail } from '../api/errors'
import type { components } from '../api/schema'
import CategoryTransactions from '../components/dashboard/CategoryTransactions'
import FloorCard from '../components/dashboard/FloorCard'
import HistoryChart, { UNCATEGORIZED_COLOR } from '../components/dashboard/HistoryChart'
import { brl, monthLabel, pct } from '../format'

type Summary = components['schemas']['SummaryDTO']
type History = components['schemas']['HistoryDTO']

function query(filters: { bank: string; accountKind: string }, extra: Record<string, string> = {}) {
  const params = new URLSearchParams(extra)
  if (filters.bank) params.set('bank', filters.bank)
  if (filters.accountKind) params.set('account_kind', filters.accountKind)
  return params.toString()
}

export default function DashboardPage() {
  const [bank, setBank] = useState('')
  const [accountKind, setAccountKind] = useState('')
  const [month, setMonth] = useState<string | null>(null)
  const [history, setHistory] = useState<History | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    fetch(`/api/dashboard/history?${query({ bank, accountKind })}`)
      .then(async (response) => {
        if (!current) return
        if (!response.ok) return setError(await errorDetail(response))
        const data = (await response.json()) as History
        setError(null)
        setHistory(data)
        setMonth((selected) => {
          const months = data.months.map((m) => m.month)
          return selected && months.includes(selected) ? selected : (months.at(-1) ?? null)
        })
      })
      .catch(() => current && setError('API indisponível'))
    return () => {
      current = false
    }
  }, [bank, accountKind])

  useEffect(() => {
    if (!month) return
    let current = true
    fetch(`/api/dashboard/summary?${query({ bank, accountKind }, { month })}`)
      .then(async (response) => {
        if (!current) return
        if (response.ok) setSummary((await response.json()) as Summary)
        else setError(await errorDetail(response))
      })
      .catch(() => current && setError('API indisponível'))
    return () => {
      current = false
    }
  }, [month, bank, accountKind])

  function selectMonth(value: string) {
    setMonth(value)
    setExpanded(null)
  }

  function changeFilter(set: (value: string) => void, value: string) {
    set(value)
    setExpanded(null)
  }

  const filtered = bank !== '' || accountKind !== ''
  const empty = history !== null && history.months.length === 0
  const shown = month !== null && summary?.month === month ? summary : null

  return (
    <section>
      <h1>Dashboard</h1>
      <p className="placeholder-note">Despesas do mês por categoria e histórico mensal.</p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <div className="dashboard-filters">
        <label>
          Mês{' '}
          <select
            value={month ?? ''}
            onChange={(e) => selectMonth(e.target.value)}
            disabled={!history || history.months.length === 0}
          >
            {history?.months
              .slice()
              .reverse()
              .map((m) => (
                <option key={m.month} value={m.month}>
                  {monthLabel(m.month)}
                </option>
              ))}
          </select>
        </label>
        <label>
          Banco{' '}
          <select value={bank} onChange={(e) => changeFilter(setBank, e.target.value)}>
            <option value="">Todos</option>
            <option value="nubank">Nubank</option>
            <option value="itau">Itaú</option>
          </select>
        </label>
        <label>
          Tipo{' '}
          <select value={accountKind} onChange={(e) => changeFilter(setAccountKind, e.target.value)}>
            <option value="">Todos</option>
            <option value="conta">Conta</option>
            <option value="cartao">Cartão</option>
          </select>
        </label>
      </div>

      {history === null && !error && <p className="placeholder-note">Carregando…</p>}

      {empty && !filtered && (
        <p className="placeholder-note">
          Nenhuma despesa ainda. Comece em <Link to="/importar">Importar</Link> enviando um extrato
          ou fatura.
        </p>
      )}
      {empty && filtered && (
        <p className="placeholder-note">Sem despesas para os filtros escolhidos.</p>
      )}

      {history && !empty && month && (
        <>
          <div className="kpi" aria-live="polite">
            <div>
              <div className="note">Total de {monthLabel(month)}</div>
              <div className="kpi-value">{shown ? brl(shown.total_cents) : '—'}</div>
            </div>
            {shown && (
              <div>
                <div className="note">vs. {monthLabel(shown.previous_month)}</div>
                <div className="kpi-delta" data-direction={shown.delta_cents > 0 ? 'up' : 'down'}>
                  {shown.delta_cents > 0 ? '+' : ''}
                  {brl(shown.delta_cents)}
                  {shown.delta_pct !== null && (
                    <>
                      {' '}
                      ({shown.delta_pct > 0 ? '+' : ''}
                      {pct(shown.delta_pct)})
                    </>
                  )}
                  {shown.delta_pct === null && <span className="note"> sem base de comparação</span>}
                </div>
              </div>
            )}
          </div>

          <FloorCard month={month} />

          <h2>Por categoria</h2>
          {shown && shown.categories.length === 0 ? (
            <p className="placeholder-note">Sem despesas em {monthLabel(month)}.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Categoria</th>
                  <th>Transações</th>
                  <th>Valor</th>
                  <th>% do total</th>
                </tr>
              </thead>
              <tbody>
                {shown?.categories.map((c) => {
                  const key = String(c.category_id ?? 'none')
                  const open = expanded === key
                  return (
                    <Fragment key={key}>
                      <tr>
                        <td>
                          <span
                            className="swatch"
                            style={{ background: c.color ?? UNCATEGORIZED_COLOR }}
                          />{' '}
                          <button
                            type="button"
                            className="link"
                            aria-expanded={open}
                            onClick={() => setExpanded(open ? null : key)}
                          >
                            {c.name}
                          </button>
                        </td>
                        <td>{c.count}</td>
                        <td>{brl(c.total_cents)}</td>
                        <td>
                          {c.pct !== null ? pct(c.pct) : '—'}
                          {c.pct !== null && c.pct > 0 && (
                            <div
                              className="share-bar"
                              style={{
                                width: `${Math.min(c.pct, 100)}%`,
                                background: c.color ?? UNCATEGORIZED_COLOR,
                              }}
                            />
                          )}
                        </td>
                      </tr>
                      {open && (
                        <tr>
                          <td colSpan={4}>
                            <CategoryTransactions
                              month={month}
                              categoryId={c.category_id}
                              filters={{ bank, accountKind }}
                            />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          )}

          <h2>Histórico</h2>
          <HistoryChart history={history} selected={month} onSelect={selectMonth} />
          <table>
            <thead>
              <tr>
                <th>Mês</th>
                <th>Total</th>
                <th>Por categoria</th>
              </tr>
            </thead>
            <tbody>
              {history.months
                .slice()
                .reverse()
                .map((m) => (
                  <tr key={m.month} data-selected={m.month === month}>
                    <td>{monthLabel(m.month)}</td>
                    <td>{brl(m.total_cents)}</td>
                    <td className="note">
                      {m.by_category
                        .filter((v) => v.total_cents !== 0)
                        .map((v) => {
                          const name =
                            history.categories.find((c) => c.id === v.category_id)?.name ??
                            'Sem categoria'
                          return `${name} ${brl(v.total_cents)}`
                        })
                        .join(' · ')}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
