import { useEffect, useRef, useState } from 'react'

// Copies text to the clipboard, with a visible confirmation and a manual
// fallback.
//
// DESIGN DECISION: the fallback is not optional polish. navigator.clipboard is
// unavailable outside a secure context and can be denied by policy or by the
// user, and it rejects silently enough that the button would just appear to do
// nothing. On failure the text is revealed, pre-selected, so Ctrl+C still works
// - the user's data is never trapped behind a permission they cannot grant.

interface CopyButtonProps {
  text: string
  label: string
  disabled?: boolean
}

type State = 'idle' | 'copied' | 'failed'

export function CopyButton({ text, label, disabled = false }: CopyButtonProps) {
  const [state, setState] = useState<State>('idle')
  const fallbackRef = useRef<HTMLTextAreaElement>(null)
  const timer = useRef<number | undefined>(undefined)

  // Clear a pending "copied" reset if the component goes away first, so it
  // cannot fire setState on an unmounted component.
  useEffect(() => () => window.clearTimeout(timer.current), [])

  async function copy() {
    window.clearTimeout(timer.current)
    try {
      await navigator.clipboard.writeText(text)
      setState('copied')
      timer.current = window.setTimeout(() => setState('idle'), 2000)
    } catch {
      setState('failed')
    }
  }

  // Select the fallback text as soon as it appears, so the only remaining step
  // is Ctrl+C.
  useEffect(() => {
    if (state === 'failed') fallbackRef.current?.select()
  }, [state])

  return (
    <div className="copy">
      <button
        type="button"
        className="primary"
        disabled={disabled}
        onClick={() => void copy()}
      >
        {state === 'copied' ? 'Copied ✓' : label}
      </button>

      {state === 'failed' && (
        <div className="copy-fallback">
          <p className="detail fail">
            Could not reach the clipboard. Press Ctrl+C to copy the selected
            text below.
          </p>
          <textarea
            ref={fallbackRef}
            className="fallback-text"
            readOnly
            rows={6}
            value={text}
          />
        </div>
      )}
    </div>
  )
}
