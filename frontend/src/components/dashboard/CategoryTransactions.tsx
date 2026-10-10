import { useEffect, useState } from 'react'
import { errorDetail } from '../../api/errors'
import type { components } from '../../api/schema'
import { brl } from '../../format'

type Transaction = components['schemas']['TransactionDTO']
type Page = components['schemas']['TransactionPageDTO']

export type Filters = { bank: string; accountKind: string }

/** Drill-down: as despesas reais que compõem a categoria no mês, com os mesmos filtros do total. */
export default function CategoryTransactions({
  month,
  categoryId,
  filters,
}: {
  month: string
  categoryId: number | null
  filters: Filters
}) {
  const [items, setItems] = useState<Transaction[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams({ month, kind: 'despesa', status: 'real', limit: '500' })
    if (categoryId === null) params.set('without_category', 'true')
    else params.set('category_id', String(categoryId))
    if (filters.bank) params.set('bank', filters.bank)
    if (filters.accountKind) params.set('account_kind', filters.accountKind)

    let current = true
    fetch(`/api/transactions?${params}`)
      .then(async (response) => {
        if (!current) return
        if (response.ok) setItems(((await response.json()) as Page).items)
        else setError(await errorDetail(response))
      })
      .catch(() => current && setError('API indisponível'))
    return () => {
      current = false
    }
  }, [month, categoryId, filters.bank, filters.accountKind])

  if (error) return <p className="error" role="alert">{error}</p>
  if (items === null) return <p className="placeholder-note">Carregando…</p>

  return (
    <table className="review-transactions">
      <thead>
        <tr>
          <th>Data</th>
          <th>Descrição</th>
          <th>Conta</th>
          <th>Valor</th>
        </tr>
      </thead>
      <tbody>
        {items.map((t) => (
          <tr key={t.id}>
            <td>{new Date(`${t.occurred_on}T00:00:00`).toLocaleDateString('pt-BR')}</td>
            <td>{t.description_raw}</td>
            <td>{t.account_name}</td>
            <td>{brl(t.amount_cents)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
