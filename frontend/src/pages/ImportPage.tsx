import { useCallback, useEffect, useState } from 'react'
import type { DragEvent, FormEvent } from 'react'
import type { components } from '../api/schema'

type ImportResult = components['schemas']['ImportResultDTO']
type ImportBatch = components['schemas']['ImportBatchDTO']

const STATUS_LABEL: Record<ImportResult['status'], string> = {
  importado: 'Importado',
  ja_importado: 'Duplicado (arquivo já importado)',
  rejeitado: 'Rejeitado',
  erro: 'Erro',
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // corpo sem JSON: usa o status
  }
  return `HTTP ${response.status}`
}

function HolderForm({ result, onSaved }: { result: ImportResult; onSaved: () => void }) {
  const [holder, setHolder] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const response = await fetch(`/api/accounts/${result.account_id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ holder }),
    })
    if (response.ok) onSaved()
    else setError(await errorDetail(response))
  }

  return (
    <form className="holder-form" onSubmit={submit}>
      <label>
        Titular da conta {result.account_name}{' '}
        <input value={holder} onChange={(e) => setHolder(e.target.value)} required />
      </label>
      <button type="submit">Salvar titular</button>
      {error && <span className="error">{error}</span>}
    </form>
  )
}

export default function ImportPage() {
  const [results, setResults] = useState<ImportResult[]>([])
  const [batches, setBatches] = useState<ImportBatch[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadBatches = useCallback(async () => {
    const response = await fetch('/api/imports')
    if (response.ok) setBatches((await response.json()) as ImportBatch[])
    else setError(await errorDetail(response))
  }, [])

  useEffect(() => {
    fetch('/api/imports')
      .then((response) => (response.ok ? (response.json() as Promise<ImportBatch[]>) : []))
      .then(setBatches)
      .catch(() => setError('API indisponível'))
  }, [])

  async function upload(files: FileList | File[]) {
    if (files.length === 0) return
    const form = new FormData()
    for (const file of Array.from(files)) form.append('files', file)
    setUploading(true)
    setError(null)
    try {
      const response = await fetch('/api/imports', { method: 'POST', body: form })
      if (response.ok) setResults((await response.json()) as ImportResult[])
      else setError(await errorDetail(response))
    } catch {
      setError('API indisponível')
    } finally {
      setUploading(false)
      void loadBatches()
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    void upload(event.dataTransfer.files)
  }

  async function undo(batch: ImportBatch) {
    if (!window.confirm(`Desfazer a importação de ${batch.filename}?`)) return
    const response = await fetch(`/api/imports/${batch.id}`, { method: 'DELETE' })
    if (!response.ok) setError(await errorDetail(response))
    else setError(null)
    setResults((current) => current.filter((r) => r.batch_id !== batch.id))
    void loadBatches()
  }

  function holderSaved(accountId: number | null) {
    setResults((current) =>
      current.map((r) => (r.account_id === accountId ? { ...r, needs_holder: false } : r)),
    )
    void loadBatches()
  }

  const needHolder = results.filter((r) => r.needs_holder)
  const pendingAccounts = needHolder.filter(
    (r, i) => needHolder.findIndex((o) => o.account_id === r.account_id) === i,
  )

  return (
    <section>
      <h1>Importar</h1>
      <p className="placeholder-note">Envie os extratos e faturas exportados pelos bancos.</p>

      <label
        className="dropzone"
        data-dragging={dragging}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        {uploading ? 'Importando…' : 'Arraste arquivos aqui ou clique para selecionar'}
        <input
          type="file"
          multiple
          hidden
          aria-label="Selecionar arquivos"
          onChange={(e) => {
            void upload(e.target.files ?? [])
            e.target.value = ''
          }}
        />
      </label>

      {error && <p className="error" role="alert">{error}</p>}

      {pendingAccounts.map((r) => (
        <HolderForm key={r.account_id} result={r} onSaved={() => holderSaved(r.account_id)} />
      ))}

      {results.length > 0 && (
        <>
          <h2>Resultado</h2>
          <table>
            <thead>
              <tr>
                <th>Arquivo</th>
                <th>Situação</th>
                <th>Novas</th>
                <th>Duplicadas</th>
                <th>Erro</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={`${r.filename}-${i}`} data-status={r.status}>
                  <td>{r.filename}</td>
                  <td>
                    {STATUS_LABEL[r.status]}
                    {r.message && r.status !== 'importado' && <div className="note">{r.message}</div>}
                    {r.errors.map((e) => (
                      <div className="note" key={e.line_no}>
                        linha {e.line_no}: {e.reason}
                      </div>
                    ))}
                  </td>
                  <td>{r.rows_new}</td>
                  <td>{r.rows_duplicate}</td>
                  <td>{r.rows_error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h2>Importações</h2>
      {batches.length === 0 ? (
        <p className="placeholder-note">Nenhuma importação ainda.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Arquivo</th>
              <th>Conta</th>
              <th>Titular</th>
              <th>Importado em</th>
              <th>Novas</th>
              <th>Duplicadas</th>
              <th>Erro</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {batches.map((b) => (
              <tr key={b.id}>
                <td>{b.filename}</td>
                <td>{b.account_name}</td>
                <td>{b.holder ?? '—'}</td>
                <td>{new Date(b.imported_at).toLocaleString('pt-BR')}</td>
                <td>{b.rows_new}</td>
                <td>{b.rows_duplicate}</td>
                <td>{b.rows_error}</td>
                <td>
                  <button type="button" onClick={() => void undo(b)}>
                    Desfazer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
