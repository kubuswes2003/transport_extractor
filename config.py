# config.py
"""Configuration settings for the transport document extractor"""

import os

# Folders
PDFS_FOLDER = "pdfs"
OUTPUT_FOLDER = "results"

# File patterns
PDF_EXTENSION = ".pdf"

# Validation ranges
FRACHT_MIN = 50
FRACHT_MAX = 5000

# Output files
JSON_OUTPUT = "extraction_results.json"

# City extraction (optional spaCy support)
USE_SPACY_CITIES = True
SPACY_CITY_MODELS = ['pl_core_news_sm', 'de_core_news_sm']
CITY_SECTION_MAX_LINES = 30

# Database configuration
DB_PATH = "transport_orders.db"
DEFAULT_EUR_PLN_RATE = 4.25
AUTOBAHN_RATE_PER_KM = 0.35

# Google Sheets configuration
# The spreadsheet is company-internal, so its id comes from the environment
# rather than from this file.
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE", os.path.join("utils", "credentials.json")
)
ENABLE_SHEETS_EXPORT = False  # SQLite is now primary storage