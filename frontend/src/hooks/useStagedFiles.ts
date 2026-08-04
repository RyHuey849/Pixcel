import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * The list of images waiting to be processed, and their preview URLs.
 *
 * DESIGN DECISION: object-URL lifetime lives in this hook rather than in a
 * component effect. An effect keyed on the file list would revoke and recreate
 * every URL whenever one file was added, which makes every thumbnail flicker.
 * Creating a URL exactly when a file is staged and revoking it exactly when that
 * file leaves is the only pairing that survives reordering and removal - the
 * browser holds the whole file alive until its URL is revoked, so missing one
 * leaks the image for the life of the page.
 */

export interface StagedFile {
  id: string
  file: File
  previewUrl: string
}

/** Identity for de-duplication - the File API exposes nothing more stable. */
function signature(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`
}

export function useStagedFiles() {
  const [files, setFiles] = useState<StagedFile[]>([])

  // Mirrors `files` so the unmount cleanup below can see the current list
  // without re-running - the effect deliberately has no dependencies.
  const latest = useRef<StagedFile[]>(files)
  latest.current = files

  useEffect(() => {
    return () => {
      for (const staged of latest.current) URL.revokeObjectURL(staged.previewUrl)
    }
  }, [])

  const add = useCallback((incoming: File[]) => {
    setFiles((current) => {
      // Dropping the same batch twice is easy to do by accident, and duplicates
      // would be parsed twice and reported twice. Skip files already staged.
      const seen = new Set(current.map((staged) => signature(staged.file)))
      const added: StagedFile[] = []
      for (const file of incoming) {
        if (seen.has(signature(file))) continue
        seen.add(signature(file))
        added.push({
          id: crypto.randomUUID(),
          file,
          previewUrl: URL.createObjectURL(file),
        })
      }
      // Appended, not prepended: upload order is the order results come back in,
      // so the staged list reads the same way as the output.
      return added.length > 0 ? [...current, ...added] : current
    })
  }, [])

  const remove = useCallback((id: string) => {
    setFiles((current) => {
      const target = current.find((staged) => staged.id === id)
      if (!target) return current
      URL.revokeObjectURL(target.previewUrl)
      return current.filter((staged) => staged.id !== id)
    })
  }, [])

  const clear = useCallback(() => {
    setFiles((current) => {
      for (const staged of current) URL.revokeObjectURL(staged.previewUrl)
      return []
    })
  }, [])

  return { files, add, remove, clear }
}
