import { useEffect, useState } from 'react'
import type { components } from '../api/schema'

type HealthResponse = components['schemas']['HealthResponse']
type ApiStatus = 'carregando' | 'ok' | 'indisponível'

export default function HealthIndicator() {
  const [status, setStatus] = useState<ApiStatus>('carregando')

  useEffect(() => {
    fetch('/api/health')
      .then((response) => (response.ok ? (response.json() as Promise<HealthResponse>) : null))
      .then((body) => setStatus(body?.status === 'ok' ? 'ok' : 'indisponível'))
      .catch(() => setStatus('indisponível'))
  }, [])

  return (
    <span className="health" data-status={status}>
      API: {status}
    </span>
  )
}
