# Pixcel

Extracts Name and three stat columns from MapleStory screenshots via OCR,
presents them in an editable table, and lets you copy the result straight into
Google Sheets.

The OCR is deliberately not generic: every screenshot comes from the same UI at
the same resolution, so the table geometry is hard-coded.

## Layout

```
backend/          FastAPI app + the OCR pipeline
  main.py           API (currently just GET /api/health)
  extract.py        crops each cell and runs Tesseract
  preprocessing.py  per-cell image pipeline feeding the OCR
  benchmark.py      scores the pipeline against ground_truth.json
frontend/         Vite + React + TypeScript
  src/api/client.ts typed backend calls
sample pictures/  test screenshots
ground_truth.json expected values for those screenshots
```

## Prerequisites

- Node 20+
- Python 3.11+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) on `PATH`
  (needed by the extraction pipeline, not by the health check)

## Setup

```powershell
# backend
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt

# frontend
cd frontend; npm install
```

## Running

Two terminals:

```powershell
# terminal 1 - API on http://127.0.0.1:8000
cd backend; .venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000

# terminal 2 - app on http://localhost:5173
cd frontend; npm run dev
```

The Vite dev server proxies `/api` to the backend, so the React code only ever
issues same-origin requests and no backend URL is baked into the bundle.

Open http://localhost:5173 — pick one or more screenshots and the parsed rows
appear below.

## API

Interactive docs at http://127.0.0.1:8000/docs.

### `GET /api/health`

Liveness probe. `{"status": "ok", "service": "pixcel-api"}`

### `POST /api/parse`

Multipart upload of one or more screenshots, as repeated `files` parts. Results
come back in upload order.

```json
[
  {
    "filename": "page1.png",
    "rows": [{ "name": "Aefher", "stat1": 8, "stat2": 0, "stat3": 0 }]
  }
]
```

Returns `400` naming the file if one cannot be decoded or holds no recognisable
table — an empty row list is reserved for a screenshot of a genuinely empty
table, so the two cases stay distinguishable.

## Benchmarking the OCR

```powershell
cd backend; .venv/Scripts/python.exe benchmark.py
```
