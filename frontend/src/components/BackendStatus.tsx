import { useEffect, useState } from 'react'
import { getHealth, type Health } from '../api/client'

// Connectivity indicator. Kept around past its original milestone because it
// distinguishes "the backend is down" from "the upload failed", which are the
// two things that go wrong in development and look alike from the UI.

type Status =
  | { state: 'loading' }
  | { state: 'connected'; health: Health }
  | { state: 'error'; message: string }

export function BackendStatus() {
  const [status, setStatus] = useState<Status>({ state: 'loading' })

  useEffect(() => {
    // `cancelled` guards against a state update after unmount, which React's
    // StrictMode double-invoke in development would otherwise trigger.
    let cancelled = false

    getHealth()
      .then((health) => {
        if (!cancelled) setStatus({ state: 'connected', health })
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setStatus({
            state: 'error',
            message: error instanceof Error ? error.message : String(error),
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (status.state === 'loading') {
    return <p className="detail">Checking backend…</p>
  }

  if (status.state === 'connected') {
    return (
      <p className="detail ok">
        Connected to <code>{status.health.service}</code>
      </p>
    )
  }

  return (
    <div className="fail">
      <p>Could not reach the backend.</p>
      <p className="detail">{status.message}</p>
      <p className="detail">
        Start it with <code>uvicorn main:app --reload --port 8000</code> from{' '}
        <code>backend/</code>.
      </p>
    </div>
  )
}
