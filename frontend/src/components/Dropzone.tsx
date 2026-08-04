import { useRef, useState } from 'react'

// Drag-and-drop target that is also a plain file picker.
//
// DESIGN DECISION: the drop area is a <label> wrapping a visually hidden
// <input type="file">. Dragging and clicking then share one control, and the
// input keeps the native keyboard and screen-reader behaviour that a <div> with
// drop handlers would have thrown away.

interface DropzoneProps {
  onFiles: (files: File[]) => void
  disabled?: boolean
}

/** Ignore anything dragged in that is not an image (folders, text, links). */
function imagesOnly(files: FileList): File[] {
  return Array.from(files).filter((file) => file.type.startsWith('image/'))
}

export function Dropzone({ onFiles, disabled = false }: DropzoneProps) {
  const [dragging, setDragging] = useState(false)
  // Drag events fire for every child element, so entering a nested node emits a
  // dragleave for the parent. Counting enter/leave pairs keeps the highlight
  // stable instead of flickering as the pointer crosses the label's contents.
  const depth = useRef(0)

  function reset() {
    depth.current = 0
    setDragging(false)
  }

  return (
    <label
      className={`dropzone${dragging ? ' dragging' : ''}${disabled ? ' disabled' : ''}`}
      onDragEnter={(event) => {
        event.preventDefault()
        if (disabled) return
        depth.current += 1
        setDragging(true)
      }}
      onDragOver={(event) => {
        // Without preventDefault the browser treats the drop as navigation and
        // opens the image in the tab instead of handing it to the page.
        event.preventDefault()
      }}
      onDragLeave={() => {
        depth.current -= 1
        if (depth.current <= 0) reset()
      }}
      onDrop={(event) => {
        event.preventDefault()
        reset()
        if (disabled) return
        const images = imagesOnly(event.dataTransfer.files)
        if (images.length > 0) onFiles(images)
      }}
    >
      <input
        type="file"
        accept="image/*"
        multiple
        disabled={disabled}
        className="visually-hidden"
        onChange={(event) => {
          if (event.target.files) onFiles(imagesOnly(event.target.files))
          // Clear the value so picking the same file again still fires change -
          // otherwise re-adding a file you just removed appears to do nothing.
          event.target.value = ''
        }}
      />
      <span className="dropzone-title">
        Drop screenshots here, or click to browse
      </span>
      <span className="detail">PNG or JPEG — multiple files supported</span>
    </label>
  )
}
