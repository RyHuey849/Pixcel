"""
FastAPI application.

Two endpoints: a health check, and POST /api/parse, which runs the OCR pipeline
in extract.py over one or more uploaded screenshots.

Run from this directory:
    .venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000
"""

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from extract import decode_image, extract_image

# DESIGN DECISION: routes are namespaced under /api. The Vite dev server proxies
# that one prefix to this app, so the frontend only ever calls same-origin
# relative URLs and there is no backend host hard-coded in the React code.
API_PREFIX = "/api"

# The Vite dev server's default origins. Only needed for requests that bypass the
# proxy (a browser hitting the API directly, or a future non-proxied client) -
# proxied calls arrive same-origin and never trigger CORS. Listed explicitly
# rather than "*" so the allowed set stays obvious.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# A screenshot of this UI is well under a megabyte. The bound exists so a stray
# large file is rejected before it is decoded into memory, not to be restrictive.
MAX_UPLOAD_BYTES = 16 * 1024 * 1024

app = FastAPI(
    title="Pixcel API",
    description="OCR extraction for MapleStory screenshots.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Health(BaseModel):
    """Response model for the health check.

    Declared as a model rather than a bare dict so the shape is enforced here and
    published in the OpenAPI schema, which is what the frontend's matching
    TypeScript type is written against.
    """

    status: str
    service: str


class Row(BaseModel):
    """One parsed table row.

    DESIGN DECISION: the API says stat1/stat2/stat3 while the pipeline's dicts
    use stat_1/stat_2/stat_3. The pipeline keys are not renamed because
    ground_truth.json and benchmark.py are written against them; the translation
    lives in to_row() below, so the wire contract and the OCR internals can move
    independently.
    """

    name: str
    stat1: int
    stat2: int
    stat3: int


class FileResult(BaseModel):
    """Every row found in one uploaded screenshot."""

    filename: str
    rows: list[Row]


def to_row(record: dict) -> Row:
    """Translate one pipeline record into the API's row shape."""
    return Row(
        name=record["name"],
        stat1=record["stat_1"],
        stat2=record["stat_2"],
        stat3=record["stat_3"],
    )


@app.get(f"{API_PREFIX}/health", response_model=Health)
def health() -> Health:
    """Liveness probe, and the frontend's connectivity test."""
    return Health(status="ok", service="pixcel-api")


# DESIGN DECISION: declared `def`, not `async def`. OCR is blocking CPU work -
# on an async route it would stall the event loop for the whole request and
# serialise every other caller behind it. A sync route is handed to FastAPI's
# threadpool instead, so uploads are processed without blocking the server.
@app.post(f"{API_PREFIX}/parse", response_model=list[FileResult])
def parse(
    files: Annotated[list[UploadFile], File(description="Screenshots to parse")],
) -> list[FileResult]:
    """Run the OCR pipeline over one or more screenshots.

    Results come back in upload order, one entry per file, so the caller can pair
    them with what it sent without matching on filename.

    A file that cannot be decoded, or that holds no recognisable table, fails the
    whole request with a 400 naming the file. That is deliberate: silently
    returning an empty row list for a bad upload looks identical to a screenshot
    of an empty table, and the user would have no way to tell which happened.
    """
    results = []
    for upload in files:
        # UploadFile.filename is Optional - a multipart part can omit it.
        filename = upload.filename or "unnamed"

        # .file is the underlying synchronous file object. The async .read()
        # cannot be awaited from this sync route, and does not need to be: the
        # body has already been received by the time the route runs.
        data = upload.file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"{filename}: file is larger than "
                       f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            )

        try:
            gray = decode_image(data)
            records = extract_image(gray)
        except ValueError as error:
            # Both decode_image() and the grid search raise ValueError for input
            # that is not a screenshot of this table - a client error, not a bug.
            raise HTTPException(
                status_code=400, detail=f"{filename}: {error}"
            ) from error

        results.append(
            FileResult(filename=filename, rows=[to_row(r) for r in records])
        )

    return results
