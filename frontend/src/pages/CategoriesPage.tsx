import { useEffect, useState } from 'react'
import { errorDetail } from '../api/errors'
import type { components } from '../api/schema'

type Category = components['schemas']['CategoryDTO']
type Deleted = components['schemas']['CategoryDeletedDTO']

const DEFAULT_COLOR = '#757575'

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState(DEFAULT_COLOR)
  const [editing, setEditing] = useState<number | null>(null)
  const [draftName, setDraftName] = useState('')
  const [draftColor, setDraftColor] = useState(DEFAULT_COLOR)

  useEffect(() => {
    let current = true
    fetch('/api/categories')
      .then(async (response) => {
        if (!current) return
        if (!response.ok) return setError(await errorDetail(response))
        setCategories((await response.json()) as Category[])
      })
      .catch(() => current && setError('API indisponível'))
    return () => {
      current = false
    }
  }, [reload])

  // Todas as ações seguem o mesmo ciclo: chamar a API, mostrar o erro e recarregar a lista.
  async function send(url: string, method: string, body?: object): Promise<Response | null> {
    setError(null)
    setNotice(null)
    try {
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      if (!response.ok) {
        setError(await errorDetail(response))
        return null
      }
      setReload((n) => n + 1)
      return response
    } catch {
      setError('API indisponível')
      return null
    }
  }

  async function create(event: React.FormEvent) {
    event.preventDefault()
    if (await send('/api/categories', 'POST', { name: newName, color: newColor })) {
      setNewName('')
      setNewColor(DEFAULT_COLOR)
    }
  }

  function startEdit(category: Category) {
    setEditing(category.id)
    setDraftName(category.name)
    setDraftColor(category.color)
  }

  async function saveEdit(category: Category) {
    const response = await send(`/api/categories/${category.id}`, 'PATCH', {
      name: draftName,
      color: draftColor,
    })
    if (response) setEditing(null)
  }

  async function remove(category: Category) {
    const count = category.transactions_count ?? 0
    const consequence =
      count > 0
        ? `${count} transação(ões) ficarão em "Sem categoria" e voltarão para a fila de Revisar. `
        : ''
    if (!window.confirm(`Excluir "${category.name}"? ${consequence}Isso não pode ser desfeito.`)) {
      return
    }
    const response = await send(`/api/categories/${category.id}`, 'DELETE')
    if (response) {
      const { affected_transactions } = (await response.json()) as Deleted
      setNotice(`"${category.name}" excluída. ${affected_transactions} transação(ões) sem categoria.`)
    }
  }

  return (
    <section>
      <h1>Categorias</h1>
      <p className="placeholder-note">
        Crie, edite e exclua as categorias das despesas. Ao excluir, as transações da categoria
        ficam em &quot;Sem categoria&quot; e voltam para a fila de Revisar.
      </p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="note" role="status">
          {notice}
        </p>
      )}

      <form onSubmit={create} className="dashboard-filters">
        <label>
          Nova categoria{' '}
          <input value={newName} onChange={(e) => setNewName(e.target.value)} required />
        </label>
        <label>
          Cor{' '}
          <input type="color" value={newColor} onChange={(e) => setNewColor(e.target.value)} />
        </label>
        <button type="submit">Criar</button>
      </form>

      {categories === null && !error && <p className="placeholder-note">Carregando…</p>}

      {categories !== null && (
        <table>
          <thead>
            <tr>
              <th>Categoria</th>
              <th>Transações</th>
              <th>Situação</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {categories.map((c) =>
              editing === c.id ? (
                <tr key={c.id}>
                  <td>
                    <input
                      type="color"
                      aria-label={`Cor de ${c.name}`}
                      value={draftColor}
                      onChange={(e) => setDraftColor(e.target.value)}
                    />{' '}
                    <input
                      aria-label={`Nome de ${c.name}`}
                      value={draftName}
                      onChange={(e) => setDraftName(e.target.value)}
                    />
                  </td>
                  <td>{c.transactions_count ?? 0}</td>
                  <td>{c.is_active ? 'Ativa' : 'Inativa'}</td>
                  <td>
                    <button type="button" onClick={() => saveEdit(c)}>
                      Salvar
                    </button>{' '}
                    <button type="button" onClick={() => setEditing(null)}>
                      Cancelar
                    </button>
                  </td>
                </tr>
              ) : (
                <tr key={c.id}>
                  <td>
                    <span className="swatch" style={{ background: c.color }} /> {c.name}
                  </td>
                  <td>{c.transactions_count ?? 0}</td>
                  <td>{c.is_active ? 'Ativa' : 'Inativa'}</td>
                  <td>
                    <button type="button" onClick={() => startEdit(c)}>
                      Editar
                    </button>{' '}
                    <button
                      type="button"
                      onClick={() => send(`/api/categories/${c.id}`, 'PATCH', { is_active: !c.is_active })}
                    >
                      {c.is_active ? 'Inativar' : 'Reativar'}
                    </button>{' '}
                    <button type="button" onClick={() => remove(c)}>
                      Excluir
                    </button>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      )}
    </section>
  )
}
