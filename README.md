# Transport Extractor

A desktop tool that reads Polish and German freight orders from PDF, pulls out the fields that matter, stores them in SQLite and shows weekly per-truck summaries.

## Context

Built for a small transport company and **in daily use there**. Before it existed, order details were retyped by hand from PDFs into a spreadsheet — one row per order, several dozen per week, across a handful of trucks.

Solo project, written alongside my studies.

The orders themselves are client documents, so **no PDFs, database files or extraction output are part of this repository** — they are git-ignored, and the repository has never contained any. What you see here is the tool, not the data.

## What it does

```
PDF orders  →  text extraction  →  regex fields + spaCy city detection
            →  validation & grouping by truck/week  →  SQLite  →  GUI / printable report
                                                              ↘  Google Sheets (optional)
```

The documents come from different forwarders in two languages, so a single fixed-layout parser was never an option. Each field has a list of candidate patterns tried in order — an order number appears as `Zlecenie Nr.` in Polish documents and `Speditionsauftrag Nr.` in German ones, unloading dates as `Termin rozładunku` or `Entladetermin`, and so on.

Loading and unloading **cities** are the awkward part: they sit in free-form address blocks rather than labelled fields. Those are handled with spaCy NER (`pl_core_news_sm`, `de_core_news_sm`) over the relevant section of the document, instead of trying to write a regex for every address format.

Extracted orders are grouped by **truck** and **week**, and the weekly figures (fuel, rate, totals, German motorway share) are computed per group. The GUI has three tabs — processing, database browser and statistics — and can print a per-truck weekly report.

## Tech stack

Python 3.10+ · tkinter · SQLite (WAL) · PyPDF2 · spaCy · matplotlib · gspread (optional export)

## Repository layout

```
extractors/
├── pdf_reader.py            # PDF → text
├── regex_extractor.py       # field extraction, PL + DE patterns
├── city_extractor.py        # city detection via spaCy NER
├── data_processor.py        # validation, grouping by truck/week
└── google_sheets_exporter.py
database/db_manager.py       # SQLite schema: trucks → week_tables → orders
utils/                       # helpers, Sheets connectivity check
gui.py                       # tkinter GUI (processing / database / statistics)
main.py                      # CLI entry point
config.py                    # all configuration constants
setup_windows.bat            # one-click setup on the company's Windows machine
```

## Running it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m spacy download pl_core_news_sm
python -m spacy download de_core_news_sm

mkdir -p pdfs        # put the PDFs to process here
python gui.py        # GUI
python main.py       # CLI
```

On Windows, `setup_windows.bat` does the same in one step and `run_gui.bat` starts the GUI.

Google Sheets export is off by default (`ENABLE_SHEETS_EXPORT`). To use it, put a service-account `credentials.json` in `utils/` and point the tool at a spreadsheet:

```bash
export GOOGLE_SHEET_ID=<spreadsheet id>
```

## Configuration

| Setting | Default | Meaning |
|---|---|---|
| `DB_PATH` | `transport_orders.db` | SQLite file |
| `DEFAULT_EUR_PLN_RATE` | `4.25` | EUR → PLN rate used in summaries |
| `AUTOBAHN_RATE_PER_KM` | `0.35` | German motorway cost per km (EUR) |
| `FRACHT_MIN` / `FRACHT_MAX` | `50` / `5000` | sanity range for freight price |
| `ENABLE_SHEETS_EXPORT` | `False` | optional Sheets export |
| `GOOGLE_SHEET_ID` | *(from environment)* | target spreadsheet |

## Limitations and what I would improve

- **Pattern-based, not learned.** A forwarder who changes their template breaks the corresponding patterns until they are extended, and an extracted field carries no confidence score.
- **Text-layer PDFs only.** Scanned orders would need OCR, which is not wired in.
- **The exchange rate is a constant**, not fetched from a rates API, so past weeks are valued at today's number.
- **Thin test coverage.** Week-boundary logic deserves the most tests, since orders that straddle a weekend decide which week they land in.
- No packaging — it runs from source on the target machine rather than as a signed executable.
- Code comments, GUI labels and log messages are in Polish.

## License

MIT — see [LICENSE](LICENSE).
