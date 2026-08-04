import type { Progress } from '../hooks/useParseBatch'

// Determinate progress for a sequential batch.
//
// DESIGN DECISION: a plain <div> with the progressbar role rather than the
// native <progress> element, which cannot be styled consistently across
// browsers without vendor-prefixed pseudo-elements. The ARIA attributes give
// assistive tech the same information the native element would have.

export function ProgressBar({ progress }: { progress: Progress }) {
  const { completed, total, current } = progress
  const percent = total === 0 ? 0 : Math.round((completed / total) * 100)

  return (
    <div className="progress">
      <div className="progress-labels">
        <span>
          {completed} of {total} processed
        </span>
        {/* The filename is the useful part of a multi-second wait: it says
            which image is slow, and which one to blame if it fails. */}
        {current && (
          <span className="detail progress-current" title={current}>
            {current}
          </span>
        )}
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={completed}
        aria-label="Screenshots processed"
      >
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}
