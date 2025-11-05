# utils/helpers.py
"""Helper utility functions"""

def format_currency(amount):
    """Format currency as EUR"""
    return f"{amount:.2f} EUR"


def format_date(date_str):
    """Convert DD.MM.YYYY to YYYY-MM-DD"""
    if not date_str:
        return None
    
    try:
        day, month, year = date_str.split('.')
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except:
        return None


def clean_plate_number(plate):
    """Clean and normalize license plate"""
    if not plate:
        return None
    
    plate = plate.strip().upper()
    
    # Remove everything after "/"
    if '/' in plate:
        plate = plate.split('/')[0]
    
    return plate


def print_header(text, width=70):
    """Print formatted header"""
    print("\n" + "="*width)
    print(text)
    print("="*width + "\n")


def print_separator(width=70):
    """Print separator line"""
    print("-"*width)