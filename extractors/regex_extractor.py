# extractors/regex_extractor.py
"""Regex-based data extraction module"""

import re
from utils.helpers import format_date, clean_plate_number
from config import FRACHT_MIN, FRACHT_MAX


class RegexExtractor:
    """Extract structured data using regex patterns"""
    
    def extract_all_fields(self, text, verbose=False):
        """Extract all fields from text"""
        data = {}
        
        data['zlecenie_nr'] = self._extract_order_number(text, verbose)
        data['termin_rozladunku'] = self._extract_unloading_date(text, verbose)
        data['tablica_rejestracyjna'] = self._extract_license_plate(text, verbose)
        data['fracht'] = self._extract_freight_price(text, verbose)
        
        return data
    
    def _extract_order_number(self, text, verbose=False):
        """Extract order number (format: XX/XXXXΑ)"""
        pattern = r'Zlecenie\s+Nr\.?\s*(\d{2}/\d{4}[A-Z])'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            result = match.group(1)
            if verbose:
                print(f"✅ Numer zlecenia: {result}")
            return result
        
        if verbose:
            print(f"❌ Numer zlecenia: NOT FOUND")
        return None
    
    def _extract_unloading_date(self, text, verbose=False):
        """Extract unloading date (format: DD.MM.YYYY)"""
        pattern = r'Termin\s+rozladunku[:\s]+(\d{2}\.\d{2}\.\d{4})'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            date_str = match.group(1)
            formatted = format_date(date_str)
            if verbose:
                print(f"✅ Data rozładunku: {formatted} (from: {date_str})")
            return formatted
        
        if verbose:
            print(f"❌ Data rozładunku: NOT FOUND")
        return None
    
    def _extract_license_plate(self, text, verbose=False):
        """Extract license plate"""
        patterns = [
            r'Samoch[oó]d\s*:\s*(P[LPN]\d{4,5}[A-Z]?)',
            r'Samoch[oó]d\s*:.*?(P[LPN]\d{4,5}[A-Z])',
            r'\b(P[LPN]\d{4,5}[A-Z]?)(?:/[A-Z0-9]+)?\b',
        ]
        
        for i, pattern in enumerate(patterns, 1):
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                plate = match.group(1)
                
                if re.match(r'P[LPN]\d{4,5}[A-Z]?', plate, re.IGNORECASE):
                    cleaned = clean_plate_number(plate)
                    if verbose:
                        print(f"✅ Tablica: {cleaned} (pattern {i})")
                    return cleaned
        
        if verbose:
            print(f"❌ Tablica: NOT FOUND")
        return None
    
    def _extract_freight_price(self, text, verbose=False):
        """Extract freight price in EUR"""
        patterns = [
            r'Vereinbarter\s+Frachtpreis.*?(\d{1,2}[\.\s]?\d{3},\d{2})\s*€',
            r'uzgodniony\s+Fracht.*?(\d{1,2}[\.\s]?\d{3},\d{2})\s*€',
            r'Vereinbarter\s+Frachtpreis.*?(\d{3,4},\d{2})\s*€',
            r'uzgodniony\s+Fracht.*?(\d{3,4},\d{2})\s*€',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                fracht_str = match.group(1)
                fracht_str = fracht_str.replace('.', '').replace(' ', '').replace(',', '.')
                fracht_val = float(fracht_str)
                
                if FRACHT_MIN <= fracht_val <= FRACHT_MAX:
                    if verbose:
                        print(f"✅ Fracht: {fracht_val} EUR")
                    return fracht_val
        
        if verbose:
            print(f"❌ Fracht: NOT FOUND")
        return None