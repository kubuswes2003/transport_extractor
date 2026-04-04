# Transport Extractor

Desktop application for extracting structured data from Polish/German transport PDF orders, storing in SQLite, and displaying in a professional tabbed GUI.

## Features

- **PDF extraction** — automated parsing of transport orders (Speditionsauftrag) using regex + spaCy NLP
- **Bilingual support** — handles both Polish and German transport documents
- **SQLite database** — local storage with 3-table schema (trucks → weeks → orders)
- **Tabbed GUI** — Processing, Database, and Statistics tabs with modern design
- **Weekly summaries** — auto-calculated SPALANIE, STAWKA, SUMA, AUTO DE values
- **Google Sheets export** — optional secondary export target
- **Print** — generates printable HTML reports per truck/week
- **Cross-platform** — works on macOS and Windows

## Screenshots

*Coming soon*

## Quick Start (Windows)

```bat
1. Clone the repo:     git clone https://github.com/kubuswes2003/transport_extractor.git
2. Run setup:          setup_windows.bat
3. Copy PDFs:          put your PDF files into the 'pdfs/' folder
4. Copy credentials:   put credentials.json into 'utils/' folder (for Google Sheets)
5. Launch:             run_gui.bat
```

## Quick Start (macOS)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy models
python -m spacy download pl_core_news_sm
python -m spacy download de_core_news_sm

# Create folders
mkdir -p pdfs

# Run
python gui.py        # GUI mode
python main.py       # CLI mode
```

## Project Structure

```
transport_extractor/
├── extractors/              # PDF parsing & data extraction
│   ├── pdf_reader.py        # PDF text extraction (PyPDF2)
│   ├── regex_extractor.py   # Field extraction via regex
│   ├── city_extractor.py    # City detection (spaCy NLP)
│   ├── data_processor.py    # Grouping & validation
│   └── google_sheets_exporter.py
├── database/
│   └── db_manager.py        # SQLite manager (3-table schema)
├── utils/
│   └── helpers.py           # CLI utilities
├── config.py                # All configuration constants
├── gui.py                   # Tkinter tabbed GUI
├── main.py                  # CLI entry point
├── requirements.txt
├── setup_windows.bat        # Windows one-click setup
├── run_gui.bat              # Windows GUI launcher
└── run_cli.bat              # Windows CLI launcher
```

## Configuration

Edit `config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `DB_PATH` | `transport_orders.db` | SQLite database file path |
| `DEFAULT_EUR_PLN_RATE` | `4.25` | EUR to PLN exchange rate |
| `AUTOBAHN_RATE_PER_KM` | `0.35` | German highway cost per km (EUR) |
| `ENABLE_SHEETS_EXPORT` | `False` | Enable Google Sheets export |
| `PDFS_FOLDER` | `pdfs` | Folder with input PDFs |

## Tech Stack

- **Python 3.10+**
- **tkinter** — desktop GUI
- **SQLite** — local database (WAL mode)
- **PyPDF2** — PDF text extraction
- **spaCy** — NLP city detection (pl_core_news_sm, de_core_news_sm)
- **matplotlib** — statistics charts
- **gspread** — Google Sheets API (optional)

## License

MIT
