import type { ReactNode } from 'react'

// Inline status message.
//
// DESIGN DECISION: role varies with tone. A success confirmation is polite
// ("status") so it waits for a pause in speech, while a failure is assertive
// ("alert") so it interrupts - a user who just lost a screenshot to a bad parse
// should not have to wait to hear about it.

interface NoticeProps {
  tone: 'ok' | 'fail'
  children: ReactNode
}

export function Notice({ tone, children }: NoticeProps) {
  return (
    <p
      className={`notice notice-${tone}`}
      role={tone === 'fail' ? 'alert' : 'status'}
    >
      {children}
    </p>
  )
}
