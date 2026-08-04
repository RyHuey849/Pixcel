import {
  isEdited,
  isValidStat,
  STAT_FIELDS,
  type EditableField,
  type EditableRow,
} from '../hooks/useEditableRows'

// The review table: every parsed row from every screenshot, editable in place.
//
// DESIGN DECISION: one input per cell, always rendered, rather than a
// click-to-edit grid. The point of this screen is fixing OCR mistakes, and the
// mistakes are only findable by scanning - a display mode that hides the fields
// until clicked would add a click to every fix and make the edited/invalid
// markers harder to show.

interface EditableTableProps {
  rows: EditableRow[]
  onUpdate: (id: string, field: EditableField, value: string) => void
  onRemove: (id: string) => void
  onRevert: (id: string) => void
  /** Show the source column - only useful when more than one file was parsed. */
  showSource: boolean
}

export function EditableTable({
  rows,
  onUpdate,
  onRemove,
  onRevert,
  showSource,
}: EditableTableProps) {
  return (
    <table className="edit-table">
      <thead>
        <tr>
          <th className="col-index" scope="col">
            #
          </th>
          {showSource && <th scope="col">Source</th>}
          <th scope="col">Name</th>
          <th scope="col">Stat 1</th>
          <th scope="col">Stat 2</th>
          <th scope="col">Stat 3</th>
          <th className="col-actions" scope="col">
            <span className="visually-hidden">Row actions</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => {
          const rowEdited =
            isEdited(row, 'name') ||
            STAT_FIELDS.some((field) => isEdited(row, field))

          return (
            <tr key={row.id}>
              <td className="col-index">{index + 1}</td>

              {showSource && (
                <td className="source" title={row.source}>
                  {row.source}
                </td>
              )}

              <td>
                <input
                  className={`cell${isEdited(row, 'name') ? ' edited' : ''}`}
                  value={row.name}
                  aria-label={`Name, row ${index + 1}`}
                  onChange={(event) =>
                    onUpdate(row.id, 'name', event.target.value)
                  }
                />
              </td>

              {STAT_FIELDS.map((field, statIndex) => {
                const value = row[field]
                const invalid = !isValidStat(value)
                return (
                  <td key={field}>
                    <input
                      className={[
                        'cell',
                        'num',
                        isEdited(row, field) ? 'edited' : '',
                        invalid ? 'invalid' : '',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      value={value}
                      // inputMode rather than type="number": the numeric keypad
                      // on touch devices without the spinner buttons, the scroll
                      // -wheel-changes-the-value behaviour, or the browser
                      // silently blanking input it considers malformed.
                      inputMode="numeric"
                      aria-label={`Stat ${statIndex + 1}, row ${index + 1}`}
                      aria-invalid={invalid}
                      onChange={(event) =>
                        onUpdate(row.id, field, event.target.value)
                      }
                    />
                  </td>
                )
              })}

              <td className="col-actions">
                {rowEdited && (
                  <button
                    type="button"
                    className="row-action"
                    onClick={() => onRevert(row.id)}
                    title="Undo edits to this row"
                    aria-label={`Revert row ${index + 1} to the original reading`}
                  >
                    ⤺
                  </button>
                )}
                <button
                  type="button"
                  className="row-action"
                  onClick={() => onRemove(row.id)}
                  title="Delete this row"
                  aria-label={`Delete row ${index + 1}`}
                >
                  ×
                </button>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
