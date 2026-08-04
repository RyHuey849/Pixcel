import { useState } from 'react'
import { parseImages, type FileResult } from '../api/client'

// Upload screenshots, run them through the OCR endpoint, show what came back.
//
// The results table is READ-ONLY on purpose: making it editable is its own
// milestone. This screen exists to prove the round trip works and to make the
// OCR output visible enough to spot problems in.

type State =
  | { phase: 'idle' }
  | { phase: 'parsing' }
  | { phase: 'done'; results: FileResult[] }
  | { phase: 'error'; message: string }

export function ParsePanel() {
  const [state, setState] = useState<State>({ phase: 'idle' })

  async function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return

    setState({ phase: 'parsing' })
    try {
      const results = await parseImages(Array.from(fileList))
      setState({ phase: 'done', results })
    } catch (error: unknown) {
      setState({
        phase: 'error',
        message: error instanceof Error ? error.message : String(error),
      })
    }
  }

  const totalRows =
    state.phase === 'done'
      ? state.results.reduce((sum, file) => sum + file.rows.length, 0)
      : 0

  return (
    <section>
      <label className="picker">
        <input
          type="file"
          accept="image/*"
          multiple
          disabled={state.phase === 'parsing'}
          // Reset the value so re-picking the same file still fires a change
          // event - otherwise a retry after an error appears to do nothing.
          onChange={(event) => {
            void handleFiles(event.target.files)
            event.target.value = ''
          }}
        />
      </label>

      {state.phase === 'parsing' && <p className="detail">Parsing…</p>}

      {state.phase === 'error' && (
        <p className="fail">{state.message}</p>
      )}

      {state.phase === 'done' && (
        <>
          <p className="detail">
            {totalRows} row{totalRows === 1 ? '' : 's'} from{' '}
            {state.results.length} file
            {state.results.length === 1 ? '' : 's'}
          </p>
          {state.results.map((file) => (
            <ResultTable key={file.filename} file={file} />
          ))}
        </>
      )}
    </section>
  )
}

function ResultTable({ file }: { file: FileResult }) {
  return (
    <div className="result">
      <h3>{file.filename}</h3>
      {file.rows.length === 0 ? (
        <p className="detail">No rows found.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Stat 1</th>
              <th>Stat 2</th>
              <th>Stat 3</th>
            </tr>
          </thead>
          <tbody>
            {file.rows.map((row, index) => (
              // Index key: names are not unique across a table (and OCR can
              // repeat one), while row position is stable for this render.
              <tr key={index}>
                <td>{row.name}</td>
                <td className="num">{row.stat1}</td>
                <td className="num">{row.stat2}</td>
                <td className="num">{row.stat3}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
