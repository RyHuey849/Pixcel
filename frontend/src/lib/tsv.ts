import type { EditableRow } from '../hooks/useEditableRows'

/**
 * Turns the reviewed table into the text Google Sheets expects on paste.
 *
 * DESIGN DECISION: tab-separated, not CSV. Pasting into Sheets splits on tabs
 * and newlines directly - no import dialog, no delimiter guessing, and no
 * quoting rules to get wrong. CSV pasted into a cell arrives as one column of
 * unsplit text, which is exactly what this milestone is meant to avoid.
 *
 * Kept as a pure function, separate from the clipboard call, so the format can
 * be reasoned about (and checked) without a browser.
 */

/** Column order matches the table, and the sheet the user is pasting into. */
export const HEADER = ['Name', 'Stat 1', 'Stat 2', 'Stat 3']

/**
 * Strip the characters that ARE the delimiters.
 *
 * OCR cannot produce a tab or a newline - its charset is letters, digits and
 * `._-` - but the name column is freely editable, and one pasted tab would
 * shift every following cell in that row by one column. Collapsing them to a
 * space keeps the grid aligned no matter what gets typed.
 */
function sanitize(value: string): string {
  return value.replace(/[\t\r\n]+/g, ' ').trim()
}

export interface TsvOptions {
  /** Prepend a header row. Off when appending to a sheet that already has one. */
  includeHeader?: boolean
}

export function toTsv(
  rows: EditableRow[],
  { includeHeader = false }: TsvOptions = {},
): string {
  const lines = rows.map((row) =>
    [
      sanitize(row.name),
      // Stats are validated as digit strings before copy is offered, so trimming
      // is all that is left to do - no number round-trip that could reformat
      // what the user actually typed.
      sanitize(row.stat1),
      sanitize(row.stat2),
      sanitize(row.stat3),
    ].join('\t'),
  )

  if (includeHeader) lines.unshift(HEADER.join('\t'))

  // Newline-separated. Sheets accepts \n; \r\n would leave a stray empty row on
  // some platforms.
  return lines.join('\n')
}
