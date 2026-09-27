# PDF Statement Extractor

Extract transactions from supported bank-statement PDFs into BudgetBakers-compatible CSV files. The project includes a local browser UI and independent command-line parsers.

## Supported formats

| Parser | Statements | Notes |
| --- | --- | --- |
| Mercado Pago | Credit card (TDC) and wallet | Recognizes both layouts in the same PDF. |
| BBVA credit (TDC) | Credit-card statement | Keeps the standalone parser's one-CSV-per-PDF behavior. |
| BBVA debit (TDD) | Debit-account statement | Keeps the standalone parser's separate-or-combined CSV prompt. |

The UI lets you select a parser for each group of PDFs and export one combined CSV or a ZIP containing one CSV per PDF. UI exports use the columns `date`, `amount`, `payee`, `category`, `account`, and `note`; combined results are sorted by date. All dates use `YYYY-MM-DD 12:00:00`.

## Requirements

- Python 3.9 or newer
- pip

## Install and run the UI

Create a virtual environment, install dependencies, and launch from the project root.

macOS:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

The UI opens in your default browser and listens only on your own computer (`127.0.0.1`). It reuses an existing copy if already running or selects another free port when needed.

## Run a parser independently

Each script still works without the UI. Run it with the current working directory set to the folder containing the PDFs. Quote paths containing spaces.

macOS/Linux:

```sh
cd "/path/to/folder/with/pdfs"
python "/path/to/PDF Extractor/parsers/MP_TDC_PDFx.py"
```

Windows PowerShell:

```powershell
Set-Location "C:\path\to\folder\with\pdfs"
py "C:\path\to\PDF Extractor\parsers\MP_TDC_PDFx.py"
```

Replace the script name with `BBVA_TDC_PDFx.py` or `BBVA_TDD_PDFx.py` to run either BBVA parser. The Mercado Pago and BBVA debit parsers ask whether to combine output; the BBVA credit parser writes one CSV per PDF.

## Statement dates

Some statement layouts omit the year from transaction dates. For those layouts, the parser reads the statement month and four-digit year from the PDF filename. English and Spanish month names and common abbreviations are supported. A transaction month later than the statement month is treated as belonging to the previous year, so December activity in a January 2026 statement is dated December 2025. If the filename has no recognizable month or year, the parser's fallback year is used instead.

The BBVA credit parser reads the year directly from each transaction date.

## Privacy and limitations

PDFs are processed locally and kept only in a temporary directory during a UI request. Do not commit statements or exported financial CSVs; the repository's `.gitignore` excludes PDFs, CSVs, and ZIPs by default.

The parsers expect selectable text and the statement layouts they were written for. Scanned/image-only PDFs and changed bank layouts may not parse correctly. Check exported transactions against the source statement before importing them into another service.

## Tests

Run the test suite from the project root:

```sh
python -m unittest discover -s tests -v
```

## License

No license has been selected yet. Add a license before publishing if you want others to have explicit permission to reuse or modify this project.