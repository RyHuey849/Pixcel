import { useMemo, useState } from 'react'
import { isValidStat, STAT_FIELDS, useEditableRows } from '../hooks/useEditableRows'
import { useParseBatch, type FileOutcome } from '../hooks/useParseBatch'
import { useStagedFiles } from '../hooks/useStagedFiles'
import { toTsv } from '../lib/tsv'
import { CopyButton } from './CopyButton'
import { Dropzone } from './Dropzone'
import { EditableTable } from './EditableTable'
import { Notice } from './Notice'
import { ProgressBar } from './ProgressBar'
import { Spinner } from './Spinner'
import { StagedImages } from './StagedImages'

// Stage screenshots, process them, then review, correct and copy the rows.
//
// DESIGN DECISION: processing is an explicit button rather than firing on
// selection. OCR takes seconds per image, so the user needs a chance to remove a
// wrong file before paying for it - which is the whole point of the preview
// queue. It also makes "add three more, then run" a single action.

export function ParsePanel() {
  const staged = useStagedFiles()
  const batch = useParseBatch()
  const table = useEditableRows()
  const [hasRun, setHasRun] = useState(false)
  // Off by default: the common repeat action is appending to a sheet that
  // already has headers, where a second header row would land as data.
  const [includeHeader, setIncludeHeader] = useState(false)

  async function process() {
    if (staged.files.length === 0 || batch.running) return
    setHasRun(true)
    const results = await batch.run(staged.files.map((s) => s.file))
    table.load(results)
  }

  function reset() {
    staged.clear()
    table.clear()
    batch.reset()
    setHasRun(false)
  }

  // Type predicate so `failure.message` is reachable below - a plain boolean
  // filter leaves the union unnarrowed.
  const failures = batch.outcomes.filter(
    (outcome): outcome is Extract<FileOutcome, { ok: false }> => !outcome.ok,
  )
  const parsedCount = batch.outcomes.length - failures.length

  // Counted here rather than in the table so the summary sits above it, visible
  // without scrolling a long result set.
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

  const showResults = hasRun && !batch.running

  return (
    <section>
      <Dropzone onFiles={staged.add} disabled={batch.running} />

      <StagedImages
        files={staged.files}
        onRemove={staged.remove}
        disabled={batch.running}
      />

      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={staged.files.length === 0 || batch.running}
          onClick={() => void process()}
        >
          {batch.running ? (
            <Spinner label="Processing…" />
          ) : (
            `Process ${staged.files.length} image${
              staged.files.length === 1 ? '' : 's'
            }`
          )}
        </button>

        {(staged.files.length > 0 || table.rows.length > 0) &&
          !batch.running && (
            <button type="button" className="secondary" onClick={reset}>
              Clear all
            </button>
          )}
      </div>

      {batch.running && batch.progress && (
        <ProgressBar progress={batch.progress} />
      )}

      {/* Failures are listed whether or not anything succeeded, and name the
          file so the user knows which one to replace. */}
      {showResults && failures.length > 0 && (
        <div className="failures">
          <Notice tone="fail">
            {failures.length} screenshot{failures.length === 1 ? '' : 's'} could
            not be read
            {parsedCount > 0 && ` — the other ${parsedCount} parsed fine`}.
          </Notice>
          <ul className="failure-list">
            {failures.map((failure) => (
              <li key={failure.filename}>
                <span className="failure-name">{failure.filename}</span>
                <span className="detail">{failure.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {showResults && (
        <>
          <div className="summary">
            <p className="detail">
              {table.rows.length} row{table.rows.length === 1 ? '' : 's'} from{' '}
              {parsedCount} file{parsedCount === 1 ? '' : 's'}
              {table.rows.length > 0 && ' — edit any cell to correct the OCR.'}
            </p>
            {invalidCount > 0 && (
              <p className="detail fail">
                {invalidCount} row{invalidCount === 1 ? '' : 's'} with a stat
                that is not a whole number — fix before copying.
              </p>
            )}
          </div>

          {table.rows.length > 0 && (
            <>
              <div className="export">
                <CopyButton
                  text={tsv}
                  label={`Copy ${table.rows.length} row${
                    table.rows.length === 1 ? '' : 's'
                  } for Sheets`}
                  successMessage={`${table.rows.length} row${
                    table.rows.length === 1 ? '' : 's'
                  } copied — paste into Google Sheets with Ctrl+V.`}
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
                  Copies tab-separated text — paste into Google Sheets and it
                  fills the columns directly.
                </p>
              </div>

              <EditableTable
                rows={table.rows}
                onUpdate={table.updateCell}
                onRemove={table.removeRow}
                onRevert={table.revertRow}
                showSource={parsedCount > 1}
              />
            </>
          )}

          {table.rows.length === 0 && failures.length === 0 && (
            <p className="detail">No rows found.</p>
          )}
        </>
      )}
    </section>
  )
}
