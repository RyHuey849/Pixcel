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

Open http://localhost:5173 — the page reports whether it reached the API.

## Benchmarking the OCR

```powershell
cd backend; .venv/Scripts/python.exe benchmark.py
```
