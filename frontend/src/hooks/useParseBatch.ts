import { useCallback, useState } from 'react'
import { ApiError, parseImage, type FileResult } from '../api/client'

/**
 * Runs a batch of screenshots through the OCR endpoint one at a time.
 *
 * DESIGN DECISION: a failed file does not abort the batch. Screenshots get
 * mixed in with other images by accident, and losing four good parses because
 * the fifth was a desktop wallpaper is the wrong trade - the user would have to
 * find and remove the bad one with no idea which it was. Each file's outcome is
 * recorded separately and reported alongside the rows that did come through.
 */

export interface Progress {
  /** Files finished so far - the numerator of "3 of 5". */
  completed: number
  total: number
  /** Name of the file being worked on, so the wait is attributable. */
  current: string
}

export type FileOutcome =
  | { filename: string; ok: true; result: FileResult }
  | { filename: string; ok: false; message: string }

/**
 * The server prefixes its 400s with the filename ("shot.png: could not
 * decode..."). The UI shows the filename separately, so strip the duplicate.
 */
function explain(filename: string, error: unknown): string {
  const detail =
    error instanceof ApiError
      ? error.detail
      : error instanceof Error
        ? error.message
        : String(error)

  const prefix = `${filename}: `
  return detail.startsWith(prefix) ? detail.slice(prefix.length) : detail
}

export function useParseBatch() {
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [outcomes, setOutcomes] = useState<FileOutcome[]>([])

  /** Process every file in order. Resolves with the ones that succeeded. */
  const run = useCallback(async (files: File[]): Promise<FileResult[]> => {
    setRunning(true)
    setOutcomes([])

    const collected: FileOutcome[] = []
    const succeeded: FileResult[] = []
    try {
      for (const [index, file] of files.entries()) {
        // Set before awaiting, so the bar names the file currently being read
        // rather than the one just finished.
        setProgress({ completed: index, total: files.length, current: file.name })
        try {
          const result = await parseImage(file)
          succeeded.push(result)
          collected.push({ filename: file.name, ok: true, result })
        } catch (error: unknown) {
          collected.push({
            filename: file.name,
            ok: false,
            message: explain(file.name, error),
          })
        }
        // Published per file so partial results are visible as they land.
        setOutcomes([...collected])
      }
      setProgress({
        completed: files.length,
        total: files.length,
        current: '',
      })
    } finally {
      setRunning(false)
    }

    return succeeded
  }, [])

  const reset = useCallback(() => {
    setOutcomes([])
    setProgress(null)
  }, [])

  return { running, progress, outcomes, run, reset }
}
