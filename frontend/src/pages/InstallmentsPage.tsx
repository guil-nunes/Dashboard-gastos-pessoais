import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorDetail } from '../api/errors'
import type { components } from '../api/schema'
import { brl, monthLabel } from '../format'

type Upcoming = components['schemas']['UpcomingDTO']
type Category = components['schemas']['CategoryDTO']

export default function InstallmentsPage() {
  const [data, setData] = useState<Upcoming | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    Promise.all([fetch('/api/installments/upcoming'), fetch('/api/categories')])
      .then(async ([upcoming, cats]) => {
        if (!current) return
        if (!upcoming.ok) return setError(await errorDetail(upcoming))
        setData((await upcoming.json()) as Upcoming)
        if (cats.ok) setCategories((await cats.json()) as Category[])
      })
      .catch(() => current && setError('API indisponível'))
    return () => {
      current = false
    }
  }, [])

  const categoryName = (id: number | null) =>
    id === null ? 'Sem categoria' : (categories.find((c) => c.id === id)?.name ?? '—')
  const empty = data !== null && data.months.length === 0 && data.flagged.length === 0

  return (
    <section>
      <h1>Parcelas</h1>
      <p className="placeholder-note">Parcelas já comprometidas nos próximos meses.</p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {data === null && !error && <p className="placeholder-note">Carregando…</p>}

      {empty && (
        <p className="placeholder-note">
          Nenhuma parcela futura. As parcelas aparecem depois que você importa uma fatura em{' '}
          <Link to="/importar">Importar</Link>.
        </p>
      )}

      {data && data.flagged.length > 0 && (
        <div className="flagged" role="region" aria-label="Parcelas que pedem revisão">
          <h2>Requer revisão</h2>
          <p className="note">
            A conta já tem lançamentos além do mês esperado, mas a parcela não chegou: a compra pode
            ter sido cancelada ou antecipada.
          </p>
          <table>
            <thead>
              <tr>
                <th>Compra</th>
                <th>Conta</th>
                <th>Esperada</th>
                <th>Valor</th>
                <th>Em aberto</th>
              </tr>
            </thead>
            <tbody>
              {data.flagged.map((g) => (
                <tr key={g.group_key}>
                  <td>
                    {g.description}
                    <div className="note">
                      parcela {g.next_number}/{g.total}
                    </div>
                  </td>
                  <td>{g.account_name}</td>
                  <td>
                    {monthLabel(g.expected_month)}
                    <div className="note">conta cobre até {monthLabel(g.covered_through)}</div>
                  </td>
                  <td>{brl(g.amount_cents)}</td>
                  <td>{g.remaining}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.months.length > 0 && (
        <>
          <h2>Comprometido por mês</h2>
          <table>
            <thead>
              <tr>
                <th>Mês</th>
                <th>Compras</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {data.months.map((m) => {
                const open = expanded === m.month
                return (
                  <Fragment key={m.month}>
                    <tr>
                      <td>
                        <button
                          type="button"
                          className="link"
                          aria-expanded={open}
                          onClick={() => setExpanded(open ? null : m.month)}
                        >
                          {monthLabel(m.month)}
                        </button>
                      </td>
                      <td>{m.items.length}</td>
                      <td>{brl(m.total_cents)}</td>
                    </tr>
                    {open && (
                      <tr>
                        <td colSpan={3}>
                          <table className="review-transactions">
                            <thead>
                              <tr>
                                <th>Compra</th>
                                <th>Parcela</th>
                                <th>Categoria</th>
                                <th>Conta</th>
                                <th>Valor</th>
                              </tr>
                            </thead>
                            <tbody>
                              {m.items.map((i) => (
                                <tr key={`${i.group_key}-${i.number}`}>
                                  <td>{i.description}</td>
                                  <td>
                                    {i.number}/{i.total}
                                  </td>
                                  <td>{categoryName(i.category_id)}</td>
                                  <td>{i.account_name}</td>
                                  <td>{brl(i.amount_cents)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
