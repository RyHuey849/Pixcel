# Project Context

Build a React web application that:

Accepts multiple MapleStory screenshots.
Extracts Name, Stat 1, Stat 2, and Stat 3 using OCR.
Displays the extracted data in an editable table.
Allows the user to copy the data in a format that can be pasted directly into Google Sheets.

Assume every screenshot uses the same layout and resolution.

Do not build a generic OCR solution. Assume a fixed layout and use hard-coded crop regions.

Do not write the entire application in one pass. Complete one milestone at a time and wait for approval before moving to the next milestone. Favor clean, modular code over rapid implementation. Include brief comments explaining design decisions, but avoid unnecessary complexity.

## Tech Stack

Frontend

React
TypeScript

Backend

Python
FastAPI

Libraries

OpenCV
Tesseract OCR
RapidFuzz (optional)