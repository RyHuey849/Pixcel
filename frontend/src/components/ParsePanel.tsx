import { useMemo, useState } from 'react'
import { parseImages } from '../api/client'
import { isValidStat, STAT_FIELDS, useEditableRows } from '../hooks/useEditableRows'
import { useStagedFiles } from '../hooks/useStagedFiles'
import { toTsv } from '../lib/tsv'
import { CopyButton } from './CopyButton'
import { Dropzone } from './Dropzone'
import { EditableTable } from './EditableTable'
import { Spinner } from './Spinner'
import { StagedImages } from './StagedImages'

// Stage screenshots, process them, then review and correct the rows.
//
// DESIGN DECISION: processing is an explicit button rather than firing on
// selection. OCR takes seconds per image, so the user needs a chance to remove a
// wrong file before paying for it - which is the whole point of the preview
// queue. It also makes "add three more, then run" a single request.

type Phase =
  | { status: 'idle' }
  | { status: 'processing' }
  | { status: 'done'; fileCount: number }
  | { status: 'error'; message: string }

export function ParsePanel() {
  const staged = useStagedFiles()
  const table = useEditableRows()
  const [phase, setPhase] = useState<Phase>({ status: 'idle' })
  // Off by default: the common repeat action is appending to a sheet that
  // already has headers, where a second header row would land as data.
  const [includeHeader, setIncludeHeader] = useState(false)

  const busy = phase.status === 'processing'

  async function process() {
    if (staged.files.length === 0 || busy) return

    setPhase({ status: 'processing' })
    try {
      // The staged order is the upload order, which the API preserves in its
      // response - so the table reads in the same order as the queue above.
      const results = await parseImages(staged.files.map((s) => s.file))
      table.load(results)
      setPhase({ status: 'done', fileCount: results.length })
    } catch (error: unknown) {
      setPhase({
        status: 'error',
        message: error instanceof Error ? error.message : String(error),
      })
    }
  }

  function reset() {
    staged.clear()
    table.clear()
    setPhase({ status: 'idle' })
  }

  // Counted here rather than in the table so the summary can be shown above it,
  // where it is visible without scrolling a long result set.
  const invalidCount = table.rows.filter((row) =>
    STAT_FIELDS.some((field) => !isValidStat(row[field])),
  ).length

  // DESIGN DECISION: copying is blocked while any stat is invalid, rather than
  // coercing the bad cell to 0. A silently-zeroed stat is indistinguishable
  // from a real 0 once it is sitting in the spreadsheet, and the whole point of
  // the review step is that wrong values get caught here and not there. The
  // offending cells are already outlined, so the fix is visible.
  const canCopy = table.rows.length > 0 && invalidCount === 0

  // Recomputed only when the rows or the header choice change - not on every
  // render of a table that can run to hundreds of rows.
  const tsv = useMemo(
    () => toTsv(table.rows, { includeHeader }),
    [table.rows, includeHeader],
  )

  return (
    <section>
      <Dropzone onFiles={staged.add} disabled={busy} />

      <StagedImages
        files={staged.files}
        onRemove={staged.remove}
        disabled={busy}
      />

      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={staged.files.length === 0 || busy}
          onClick={() => void process()}
        >
          {busy ? (
            <Spinner label={`Processing ${staged.files.length}…`} />
          ) : (
            `Process ${staged.files.length} image${
              staged.files.length === 1 ? '' : 's'
            }`
          )}
        </button>

        {(staged.files.length > 0 || table.rows.length > 0) && !busy && (
          <button type="button" className="secondary" onClick={reset}>
            Clear all
          </button>
        )}
      </div>

      {phase.status === 'error' && <p className="fail">{phase.message}</p>}

      {phase.status === 'done' && (
        <>
          <div className="summary">
            <p className="detail">
              {table.rows.length} row{table.rows.length === 1 ? '' : 's'} from{' '}
              {phase.fileCount} file{phase.fileCount === 1 ? '' : 's'}
              {' — edit any cell to correct the OCR.'}
            </p>
            {invalidCount > 0 && (
              <p className="detail fail">
                {invalidCount} row{invalidCount === 1 ? '' : 's'} with a stat
                that is not a whole number — fix before copying.
              </p>
            )}
          </div>

          {table.rows.length > 0 && (
            <div className="export">
              <CopyButton
                text={tsv}
                label={`Copy ${table.rows.length} row${
                  table.rows.length === 1 ? '' : 's'
                } for Sheets`}
                disabled={!canCopy}
              />
              <label className="header-toggle">
                <input
                  type="checkbox"
                  checked={includeHeader}
                  onChange={(event) => setIncludeHeader(event.target.checked)}
                />
                Include header row
              </label>
              <p className="detail">
                Copies tab-separated text — paste into Google Sheets and it fills
                the columns directly.
              </p>
            </div>
          )}

          {table.rows.length === 0 ? (
            <p className="detail">No rows found.</p>
          ) : (
            <EditableTable
              rows={table.rows}
              onUpdate={table.updateCell}
              onRemove={table.removeRow}
              onRevert={table.revertRow}
              showSource={phase.fileCount > 1}
            />
          )}
        </>
      )}
    </section>
  )
}
