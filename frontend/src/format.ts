const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const percent = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

export function brl(cents: number): string {
  return currency.format(cents / 100)
}

export function pct(value: number): string {
  return `${percent.format(value)}%`
}

/** '2026-08' → 'ago/2026' */
export function monthLabel(month: string): string {
  const [year, number] = month.split('-')
  return `${MONTHS[Number(number) - 1]}/${year}`
}
