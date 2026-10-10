export async function errorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((item: { msg?: string }) => item.msg ?? '')
        .filter(Boolean)
        .join('; ')
    }
  } catch {
    // corpo sem JSON: usa o status
  }
  return `HTTP ${response.status}`
}
