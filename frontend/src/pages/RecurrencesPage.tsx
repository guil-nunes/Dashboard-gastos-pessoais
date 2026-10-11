import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorDetail } from '../api/errors'
import type { components } from '../api/schema'
import { brl } from '../format'

type Recurrence = components['schemas']['RecurrenceDTO']

const dateLabel = (iso: string) => iso.split('-').reverse().join('/')

export default function RecurrencesPage() {
  const [items, setItems] = useState<Recurrence[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let current = true
    fetch('/api/recurrences')
      .then(async (response) => {
        if (!current) return
        if (!response.ok) return setError(await errorDetail(response))
        setError(null)
        setItems((await response.json()) as Recurrence[])
      })
      .catch(() => current && setError('API indisponível'))
    return () => {
      current = false
    }
  }, [reload])

  const mark = useCallback(async (merchantKey: string, isRecurring: boolean) => {
    try {
      const response = await fetch(`/api/recurrences/${encodeURIComponent(merchantKey)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_recurring: isRecurring }),
      })
      if (!response.ok) return setError(await errorDetail(response))
      setReload((n) => n + 1)
    } catch {
      setError('API indisponível')
    }
  }, [])

  const active = items?.filter((i) => !i.dismissed) ?? []
  const dismissed = items?.filter((i) => i.dismissed) ?? []

  return (
    <section>
      <h1>Recorrentes</h1>
      <p className="placeholder-note">
        Gastos que se repetem todo mês, como assinaturas e contas fixas: ao menos 3 lançamentos com
        cerca de 30 dias entre eles e valores parecidos.
      </p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {items === null && !error && <p className="placeholder-note">Carregando…</p>}

      {items !== null && items.length === 0 && (
        <p className="placeholder-note">
          Nenhum gasto recorrente detectado. Importe ao menos três meses em{' '}
          <Link to="/importar">Importar</Link>.
        </p>
      )}

      {active.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Estabelecimento</th>
              <th>Valor médio</th>
              <th>Último lançamento</th>
              <th>Meses</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {active.map((i) => (
              <tr key={i.merchant_key}>
                <td>{i.description}</td>
                <td>{brl(i.average_cents)}</td>
                <td>
                  {dateLabel(i.last_on)}
                  <div className="note">{brl(i.last_cents)}</div>
                </td>
                <td>{i.months_count}</td>
                <td>
                  <button type="button" onClick={() => mark(i.merchant_key, false)}>
                    Não é recorrente
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {dismissed.length > 0 && (
        <>
          <h2>Marcados como não recorrentes</h2>
          <table>
            <tbody>
              {dismissed.map((i) => (
                <tr key={i.merchant_key}>
                  <td>{i.description}</td>
                  <td>{brl(i.average_cents)}</td>
                  <td>
                    <button type="button" onClick={() => mark(i.merchant_key, true)}>
                      Desfazer
                    </button>
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
