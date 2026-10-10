import { Fragment, useCallback, useEffect, useState } from 'react'
import { errorDetail } from '../api/errors'
import type { components } from '../api/schema'
import { brl } from '../format'
import MerchantTransactions from '../components/review/MerchantTransactions'
import TargetSelect, { type Category, type Target } from '../components/review/TargetSelect'

type Merchant = components['schemas']['PendingMerchantDTO']

const SOURCE_LABEL: Record<string, string> = {
  memoria: 'memória',
  regra: 'regra',
  classificador: 'classificador',
  gemini: 'Gemini',
  manual: 'manual',
  nenhuma: 'sem sugestão',
}

export default function ReviewPage() {
  const [merchants, setMerchants] = useState<Merchant[] | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [targets, setTargets] = useState<Record<string, Target | null>>({})
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkTarget, setBulkTarget] = useState<Target | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [m, c] = await Promise.all([
        fetch('/api/merchants?pending=true'),
        fetch('/api/categories'),
      ])
      if (!m.ok) return setError(await errorDetail(m))
      if (!c.ok) return setError(await errorDetail(c))
      setMerchants((await m.json()) as Merchant[])
      setCategories((await c.json()) as Category[])
    } catch {
      setError('API indisponível')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const categoryName = (id: number | null) => categories.find((c) => c.id === id)?.name

  async function bulk(keys: string[], action: 'apply' | 'confirm', target?: Target | null) {
    setError(null)
    setNotice(null)
    let affected = 0
    for (const key of keys) {
      const body = {
        merchant_key: key,
        action,
        ...(action === 'apply' && target ? target : {}),
      }
      const response = await fetch('/api/transactions/bulk-categorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        setError(`${key}: ${await errorDetail(response)}`)
        break
      }
      affected += ((await response.json()) as { affected: number }).affected
    }
    setSelected(new Set())
    if (affected > 0) setNotice(`${affected} transações atualizadas.`)
    await load()
  }

  function toggle(key: string) {
    setSelected((current) => {
      const next = new Set(current)
      if (!next.delete(key)) next.add(key)
      return next
    })
  }

  const investment: Target = {
    kind: 'ignorar',
    category_id: null,
    ignore_reason: 'investimento',
  }

  return (
    <section>
      <h1>Revisar</h1>
      <p className="placeholder-note">
        Confirme ou corrija o tipo e a categoria das transações, por estabelecimento.
      </p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && <p className="note" role="status">{notice}</p>}

      {merchants === null ? (
        <p className="placeholder-note">Carregando…</p>
      ) : merchants.length === 0 ? (
        <p className="placeholder-note">
          Nada pendente. Importe extratos e faturas na tela Importar para começar a revisão.
        </p>
      ) : (
        <>
          <div className="review-bulk">
            <span>{selected.size} selecionados</span>
            <TargetSelect
              categories={categories}
              value={bulkTarget}
              onChange={setBulkTarget}
              label="Destino do lote"
            />
            <button
              type="button"
              disabled={selected.size === 0 || !bulkTarget}
              onClick={() => void bulk([...selected], 'apply', bulkTarget)}
            >
              Aplicar às selecionadas
            </button>
            <button
              type="button"
              disabled={selected.size === 0}
              onClick={() => void bulk([...selected], 'confirm')}
            >
              Confirmar selecionadas
            </button>
          </div>

          <table>
            <thead>
              <tr>
                <th />
                <th>Estabelecimento</th>
                <th>Transações</th>
                <th>Total</th>
                <th>Sugestão</th>
                <th>Ação</th>
              </tr>
            </thead>
            <tbody>
              {merchants.map((m) => {
                const target = targets[m.merchant_key] ?? null
                const lowConfidence = m.min_confidence !== null && m.min_confidence < 0.8
                return (
                  <Fragment key={m.merchant_key}>
                    <tr>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Selecionar ${m.merchant_key}`}
                          checked={selected.has(m.merchant_key)}
                          onChange={() => toggle(m.merchant_key)}
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="link"
                          aria-expanded={expanded === m.merchant_key}
                          onClick={() => setExpanded(expanded === m.merchant_key ? null : m.merchant_key)}
                        >
                          {m.merchant_key}
                        </button>
                        <div className="note">{m.sample_description}</div>
                      </td>
                      <td>{m.count}</td>
                      <td>{brl(m.total_cents)}</td>
                      <td>
                        {categoryName(m.category_id) ?? '—'}
                        {m.category_source && (
                          <div className="note">{SOURCE_LABEL[m.category_source]}</div>
                        )}
                        {lowConfidence && <span className="badge">baixa confiança</span>}
                        {m.suggested_ignore_reason === 'investimento' && (
                          <span className="badge">sugestão: investimento</span>
                        )}
                      </td>
                      <td className="review-actions">
                        <TargetSelect
                          categories={categories}
                          value={target}
                          onChange={(t) => setTargets({ ...targets, [m.merchant_key]: t })}
                          label={`Destino de ${m.merchant_key}`}
                        />
                        <button
                          type="button"
                          disabled={!target}
                          onClick={() => void bulk([m.merchant_key], 'apply', target)}
                        >
                          Aplicar às {m.count}
                        </button>
                        <button type="button" onClick={() => void bulk([m.merchant_key], 'confirm')}>
                          Confirmar
                        </button>
                        {m.suggested_ignore_reason === 'investimento' && (
                          <button
                            type="button"
                            onClick={() => void bulk([m.merchant_key], 'apply', investment)}
                          >
                            Marcar como investimento
                          </button>
                        )}
                      </td>
                    </tr>
                    {expanded === m.merchant_key && (
                      <tr>
                        <td />
                        <td colSpan={5}>
                          <MerchantTransactions
                            merchantKey={m.merchant_key}
                            categories={categories}
                            onChanged={() => void load()}
                            onError={setError}
                          />
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
