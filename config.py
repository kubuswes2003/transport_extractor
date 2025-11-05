# config.py
"""Configuration settings for the transport document extractor"""

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