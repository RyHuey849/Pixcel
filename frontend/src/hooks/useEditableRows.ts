import { useCallback, useState } from 'react'
import type { FileResult } from '../api/client'

/**
 * The reviewable table: every parsed row from every screenshot, in upload order,
 * with the user's edits applied on top.
 *
 * DESIGN DECISION: stats are held as STRINGS, not numbers, even though the API
 * sends and the export needs integers. A number-typed field cannot represent the
 * half-finished states editing passes through - clearing a cell to retype it
 * leaves it empty, and coercing that to 0 on every keystroke means the user
 * cannot delete the leading digit of "10" without the field fighting back. The
 * string is what the user typed; isValidStat() below decides whether it is
 * usable yet, and conversion happens once, at export.
 */

export interface EditableRow {
  id: string
  /** Filename this row came from - lets a misread be traced to its screenshot. */
  source: string
  name: string
  stat1: string
  stat2: string
  stat3: string
  /** The OCR's answer, kept so edits can be shown and reverted per row. */
  original: {
    name: string
    stat1: string
    stat2: string
    stat3: string
  }
}

/** The row fields the user can edit. */
export type EditableField = 'name' | 'stat1' | 'stat2' | 'stat3'

export const STAT_FIELDS = ['stat1', 'stat2', 'stat3'] as const

/** A stat cell is usable when it holds a non-negative integer and nothing else. */
export function isValidStat(value: string): boolean {
  return /^\d+$/.test(value.trim())
}

/** True when the user has changed this field away from what the OCR read. */
export function isEdited(row: EditableRow, field: EditableField): boolean {
  return row[field] !== row.original[field]
}

/** Flatten the API's per-file results into one ordered list of editable rows. */
function fromResults(results: FileResult[]): EditableRow[] {
  return results.flatMap((file) =>
    file.rows.map((row) => {
      const values = {
        name: row.name,
        stat1: String(row.stat1),
        stat2: String(row.stat2),
        stat3: String(row.stat3),
      }
      return {
        id: crypto.randomUUID(),
        source: file.filename,
        ...values,
        // Copied, not aliased - `values` is mutated by later edits via setState
        // replacement, and `original` must keep the OCR's answer.
        original: { ...values },
      }
    }),
  )
}

export function useEditableRows() {
  const [rows, setRows] = useState<EditableRow[]>([])

  /** Replace the table with a fresh parse. Discards edits, by design: the rows
   *  they applied to no longer exist. */
  const load = useCallback((results: FileResult[]) => {
    setRows(fromResults(results))
  }, [])

  const updateCell = useCallback(
    (id: string, field: EditableField, value: string) => {
      setRows((current) =>
        current.map((row) => (row.id === id ? { ...row, [field]: value } : row)),
      )
    },
    [],
  )

  const removeRow = useCallback((id: string) => {
    setRows((current) => current.filter((row) => row.id !== id))
  }, [])

  /** Restore one row to the OCR's original reading. */
  const revertRow = useCallback((id: string) => {
    setRows((current) =>
      current.map((row) =>
        row.id === id ? { ...row, ...row.original } : row,
      ),
    )
  }, [])

  const clear = useCallback(() => setRows([]), [])

  return { rows, load, updateCell, removeRow, revertRow, clear }
}
