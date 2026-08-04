/**
 * Typed access to the FastAPI backend.
 *
 * All backend calls go through this module so the fetch/error handling lives in
 * one place; components deal in typed results, never in Response objects.
 */

// Relative, not absolute: the Vite dev server proxies /api to FastAPI, so the
// browser always sees a same-origin request. See vite.config.ts.
const API_BASE = '/api'

/** Response shape of GET /api/health - mirrors the Health model in main.py. */
export interface Health {
  status: string
  service: string
}

/** Thrown for any non-2xx response, so callers can catch one error type. */
export class ApiError extends Error {
  // Assigned in the body rather than declared as a constructor parameter
  // property: the tsconfig sets erasableSyntaxOnly, which bars TS-only syntax
  // that has to emit runtime code.
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** One parsed table row - mirrors the Row model in main.py. */
export interface Row {
  name: string
  stat1: number
  stat2: number
  stat3: number
}

/** Rows found in one uploaded screenshot - mirrors FileResult in main.py. */
export interface FileResult {
  filename: string
  rows: Row[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    // FastAPI puts the reason in a JSON `detail` field. Surfacing it beats
    // "Bad Request", which tells the user nothing about which file failed.
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // Non-JSON error body - keep the status text.
    }
    throw new ApiError(
      `${init?.method ?? 'GET'} ${path} failed: ${detail}`,
      response.status,
    )
  }
  return (await response.json()) as T
}

/** Connectivity check against the backend. */
export function getHealth(): Promise<Health> {
  return request<Health>('/health')
}

/**
 * Upload screenshots for OCR. Results come back in upload order.
 *
 * The Content-Type header is deliberately not set: fetch derives it from the
 * FormData, including the multipart boundary, which cannot be written by hand.
 */
export function parseImages(files: File[]): Promise<FileResult[]> {
  const body = new FormData()
  // Repeated "files" parts - matches the list[UploadFile] parameter name.
  for (const file of files) body.append('files', file)
  return request<FileResult[]>('/parse', { method: 'POST', body })
}
