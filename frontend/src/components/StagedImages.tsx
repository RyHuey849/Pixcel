import type { StagedFile } from '../hooks/useStagedFiles'

// Thumbnail grid of everything queued for processing, each with a remove button.

interface StagedImagesProps {
  files: StagedFile[]
  onRemove: (id: string) => void
  disabled?: boolean
}

/** Human-readable file size, so an oversized screenshot is obvious at a glance. */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function StagedImages({
  files,
  onRemove,
  disabled = false,
}: StagedImagesProps) {
  if (files.length === 0) return null

  return (
    <ul className="staged">
      {files.map((staged, index) => (
        <li key={staged.id} className="staged-item">
          <img src={staged.previewUrl} alt="" className="thumb" />
          <div className="staged-meta">
            {/* The position is shown because it is also the result order. */}
            <span className="staged-name" title={staged.file.name}>
              {index + 1}. {staged.file.name}
            </span>
            <span className="detail">{formatSize(staged.file.size)}</span>
          </div>
          <button
            type="button"
            className="remove"
            disabled={disabled}
            onClick={() => onRemove(staged.id)}
            aria-label={`Remove ${staged.file.name}`}
          >
            ×
          </button>
        </li>
      ))}
    </ul>
  )
}
