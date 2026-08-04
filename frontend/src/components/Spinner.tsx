// Inline loading indicator.
//
// role="status" so assistive tech announces the wait; the visible label is the
// announcement, which is why the spinner graphic itself is aria-hidden.

export function Spinner({ label = 'Working…' }: { label?: string }) {
  return (
    <span className="spinner-wrap" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </span>
  )
}
