import type { components } from '../../api/schema'

export type Category = components['schemas']['CategoryDTO']

export type Target =
  | { kind: 'despesa'; category_id: number | null; ignore_reason: null }
  | { kind: 'ignorar'; category_id: null; ignore_reason: string }

const IGNORE_REASONS: Record<string, string> = {
  pagamento_fatura: 'Pagamento de fatura',
  transferencia_interna: 'Transferência interna',
  investimento: 'Investimento',
  receita: 'Receita',
  outro: 'Outro',
}

export function encodeTarget(target: Target | null): string {
  if (!target) return ''
  return target.kind === 'despesa'
    ? `cat:${target.category_id ?? ''}`
    : `ignore:${target.ignore_reason}`
}

export function decodeTarget(value: string): Target | null {
  if (value.startsWith('cat:')) {
    const id = value.slice(4)
    return { kind: 'despesa', category_id: id ? Number(id) : null, ignore_reason: null }
  }
  if (value.startsWith('ignore:')) {
    return { kind: 'ignorar', category_id: null, ignore_reason: value.slice(7) }
  }
  return null
}

export default function TargetSelect({
  categories,
  value,
  onChange,
  label,
}: {
  categories: Category[]
  value: Target | null
  onChange: (target: Target | null) => void
  label: string
}) {
  return (
    <select
      aria-label={label}
      value={encodeTarget(value)}
      onChange={(e) => onChange(decodeTarget(e.target.value))}
    >
      <option value="">Escolher…</option>
      <optgroup label="Despesa em">
        {categories
          .filter((c) => c.is_active)
          .map((c) => (
            <option key={c.id} value={`cat:${c.id}`}>
              {c.name}
            </option>
          ))}
        <option value="cat:">Despesa sem categoria</option>
      </optgroup>
      <optgroup label="Ignorar">
        {Object.entries(IGNORE_REASONS).map(([reason, text]) => (
          <option key={reason} value={`ignore:${reason}`}>
            {text}
          </option>
        ))}
      </optgroup>
    </select>
  )
}
