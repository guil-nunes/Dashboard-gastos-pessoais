import { useCallback, useEffect, useState } from 'react'
import { errorDetail } from '../../api/errors'
import type { components } from '../../api/schema'
import { brl } from '../../format'
import TargetSelect, { type Category, type Target } from './TargetSelect'

type Transaction = components['schemas']['TransactionDTO']
type Page = components['schemas']['TransactionPageDTO']

function Row({
  transaction,
  categories,
  onChanged,
  onError,
}: {
  transaction: Transaction
  categories: Category[]
  onChanged: () => void
  onError: (message: string) => void
}) {
  const [target, setTarget] = useState<Target | null>(null)

  async function send(body: object) {
    const response = await fetch(`/api/transactions/${transaction.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (response.ok) onChanged()
    else onError(await errorDetail(response))
  }

  return (
    <tr>
      <td>{new Date(`${transaction.occurred_on}T00:00:00`).toLocaleDateString('pt-BR')}</td>
      <td>{transaction.description_raw}</td>
      <td>{transaction.account_name}</td>
      <td>{brl(transaction.amount_cents)}</td>
      <td className="review-actions">
        <TargetSelect
          categories={categories}
          value={target}
          onChange={setTarget}
          label={`Categoria da transação ${transaction.id}`}
        />
        <button type="button" disabled={!target} onClick={() => target && void send(target)}>
          Aplicar
        </button>
        <button type="button" onClick={() => void send({ action: 'confirm' })}>
          Confirmar
        </button>
      </td>
    </tr>
  )
}

export default function MerchantTransactions({
  merchantKey,
  categories,
  onChanged,
  onError,
}: {
  merchantKey: string
  categories: Category[]
  onChanged: () => void
  onError: (message: string) => void
}) {
  const [items, setItems] = useState<Transaction[] | null>(null)

  const load = useCallback(async () => {
    const params = new URLSearchParams({ merchant_key: merchantKey, pending: 'true', limit: '500' })
    const response = await fetch(`/api/transactions?${params}`)
    if (response.ok) setItems(((await response.json()) as Page).items)
    else onError(await errorDetail(response))
  }, [merchantKey, onError])

  useEffect(() => {
    void load()
  }, [load])

  if (items === null) return <p className="placeholder-note">Carregando…</p>
  if (items.length === 0) return <p className="placeholder-note">Nenhuma pendente.</p>

  return (
    <table className="review-transactions">
      <thead>
        <tr>
          <th>Data</th>
          <th>Descrição</th>
          <th>Conta</th>
          <th>Valor</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {items.map((t) => (
          <Row
            key={t.id}
            transaction={t}
            categories={categories}
            onError={onError}
            onChanged={() => {
              void load()
              onChanged()
            }}
          />
        ))}
      </tbody>
    </table>
  )
}
