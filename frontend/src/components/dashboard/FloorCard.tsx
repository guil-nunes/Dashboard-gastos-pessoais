import { useEffect, useState } from 'react'
import { errorDetail } from '../../api/errors'
import type { components } from '../../api/schema'
import { brl, monthLabel } from '../../format'

type Floor = components['schemas']['FloorDTO']

export default function FloorCard({ month }: { month: string }) {
  const [floor, setFloor] = useState<Floor | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    fetch(`/api/dashboard/floor?month=${month}`)
      .then(async (response) => {
        if (!current) return
        if (!response.ok) return setError(await errorDetail(response))
        setError(null)
        setFloor((await response.json()) as Floor)
      })
      .catch(() => current && setError('API indisponível'))
    return () => {
      current = false
    }
  }, [month])

  const shown = floor !== null && floor.month === month ? floor : null

  return (
    <div className="floor" role="region" aria-label="Piso do próximo mês">
      <h2>Piso de {monthLabel(shown?.target_month ?? month)}</h2>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="kpi" aria-live="polite">
        <div>
          <div className="note">Parcelas + recorrentes já conhecidos</div>
          <div className="kpi-value">{shown ? brl(shown.total_cents) : '—'}</div>
        </div>
      </div>
      {shown && shown.total_cents === 0 && (
        <p className="placeholder-note">
          Nenhuma parcela ou gasto recorrente conhecido para {monthLabel(shown.target_month)}. É um
          piso, não uma previsão.
        </p>
      )}
      {shown && shown.installments.length > 0 && (
        <>
          <h3>Parcelas · {brl(shown.installments_cents)}</h3>
          <table>
            <tbody>
              {shown.installments.map((i) => (
                <tr key={`${i.group_key}-${i.number}`}>
                  <td>
                    {i.description}
                    <div className="note">
                      parcela {i.number}/{i.total} · {i.account_name}
                    </div>
                  </td>
                  <td>{brl(i.amount_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {shown && shown.recurrences.length > 0 && (
        <>
          <h3>Recorrentes · {brl(shown.recurrences_cents)}</h3>
          <table>
            <tbody>
              {shown.recurrences.map((r) => (
                <tr key={r.merchant_key}>
                  <td>
                    {r.description}
                    <div className="note">último valor</div>
                  </td>
                  <td>{brl(r.last_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
