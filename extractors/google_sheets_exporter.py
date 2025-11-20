# extractors/google_sheets_exporter.py
"""Google Sheets exporter for transport order data"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import calendar
import time
from typing import Optional


class GoogleSheetsExporter:
    """Export extracted transport order data to Google Sheets"""
    
    def __init__(self, sheet_id: str, credentials_path: str = 'credentials.json'):
        """Initialize Google Sheets exporter
        
        Args:
            sheet_id: Google Sheets document ID
            credentials_path: Path to service account credentials JSON file
        """
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        
        try:
            creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
            self.client = gspread.authorize(creds)
            self.sheet_id = sheet_id
            self.workbook = self.client.open_by_key(sheet_id)
        except FileNotFoundError:
            import os
            abs_path = os.path.abspath(credentials_path)
            raise FileNotFoundError(
                f"Credentials file not found: {credentials_path}\n"
                f"Absolute path checked: {abs_path}\n"
                "Please ensure the credentials file exists at the specified path."
            )
        except Exception as e:
            raise Exception(f"Failed to initialize Google Sheets client: {e}")
    
    def parse_week_identifier(self, identifier: str) -> Optional[tuple[int, int, int]]:
        """Parse week identifier string to extract month and day range
        
        Args:
            identifier: Week identifier string (e.g., "11.10-17", "11.17-24")
            
        Returns:
            Tuple of (month, start_day, end_day) or None if invalid format
        """
        import re
        
        # Pattern: month.day-day (e.g., "11.10-17", "11.17-24", "1.10-17")
        pattern = r'^(\d{1,2})\.(\d{1,2})-(\d{1,2})$'
        match = re.match(pattern, identifier.strip())
        
        if not match:
            return None
        
        try:
            month = int(match.group(1))
            start_day = int(match.group(2))
            end_day = int(match.group(3))
            
            # Validate ranges
            if 1 <= month <= 12 and 1 <= start_day <= 31 and 1 <= end_day <= 31:
                return (month, start_day, end_day)
        except (ValueError, IndexError):
            return None
        
        return None
    
    def find_week_table(self, sheet, target_date: str) -> Optional[int]:
        """Find week table row for a given date by searching for identifiers containing the date
        
        Args:
            sheet: gspread worksheet object
            target_date: Date in YYYY-MM-DD format
            
        Returns:
            Row number where week table starts, or None if not found
        """
        # Parse target date
        date = datetime.strptime(target_date, '%Y-%m-%d')
        target_month = date.month
        target_day = date.day
        
        # Try using findall with regex first (more reliable)
        try:
            # Search for pattern like "11.10-17" in column A
            all_cells = sheet.findall(r'\d+\.\d+-\d+', in_column=1)
            
            for cell in all_cells:
                cell_value = str(cell.value).strip()
                parsed = self.parse_week_identifier(cell_value)
                
                if parsed:
                    month, start_day, end_day = parsed
                    # Check if this identifier matches our target date
                    if month == target_month and start_day <= target_day <= end_day:
                        return cell.row
        except Exception as e:
            # If findall fails, try alternative method
            pass
        
        # Fallback: read all column A values manually
        try:
            # Get a reasonable range of rows to check (first 200 rows should be enough)
            max_rows_to_check = min(200, sheet.row_count)
            col_a_range = sheet.range(f'A1:A{max_rows_to_check}')
            
            for cell in col_a_range:
                if not cell.value:
                    continue
                
                cell_value_str = str(cell.value).strip()
                
                # Try to parse as week identifier
                parsed = self.parse_week_identifier(cell_value_str)
                if not parsed:
                    continue
                
                month, start_day, end_day = parsed
                
                # Check if this identifier matches our target date
                if month == target_month and start_day <= target_day <= end_day:
                    return cell.row
            
        except Exception as e:
            # Last fallback: use col_values
            try:
                col_a_values = sheet.col_values(1)
                
                for row_idx, cell_value in enumerate(col_a_values, start=1):
                    if not cell_value:
                        continue
                    
                    cell_value_str = str(cell_value).strip()
                    parsed = self.parse_week_identifier(cell_value_str)
                    
                    if parsed:
                        month, start_day, end_day = parsed
                        if month == target_month and start_day <= target_day <= end_day:
                            return row_idx
            except Exception:
                pass
        
        return None
    
    def find_insertion_position(self, sheet, table_start_row: int, target_date: str) -> Optional[int]:
        """Find first empty row in the fixed 10-position table
        
        Args:
            sheet: gspread worksheet object
            table_start_row: Row number where week table starts
            target_date: Date in YYYY-MM-DD format (not used but kept for compatibility)
            
        Returns:
            Row number of first empty position, or None if table is full
        """
        # Data rows start 2 rows after week identifier
        data_start_row = table_start_row + 2
        # Each table has exactly 10 positions
        data_end_row = data_start_row + 9  # 10 positions (0-9)
        
        try:
            # Check column B (date column) to find empty rows
            # An empty position has no date in column B
            date_range = sheet.range(f'B{data_start_row}:B{data_end_row}')
            
            for cell in date_range:
                # If cell is empty or only whitespace, this position is available
                if not cell.value or str(cell.value).strip() == '':
                    return cell.row
            
            # All 10 positions are full
            return None
                
        except Exception as e:
            # If we can't read the range, return first data row as fallback
            print(f"   ⚠️  Warning: Could not check empty positions: {e}")
            return data_start_row
    
    def find_overlapping_weeks(self, sheet, target_date: str):
        """Find all week tables that include the target date
        
        Args:
            sheet: gspread worksheet object
            target_date: Date in YYYY-MM-DD format
            
        Returns:
            List of tuples: [(row_number, week_identifier), ...]
        """
        date_obj = datetime.strptime(target_date, '%Y-%m-%d')
        found_tables = []
        
        try:
            # Get all values in column A
            col_a_values = sheet.col_values(1)
            
            # Search for week identifiers that include this date
            for row_idx, cell_value in enumerate(col_a_values, start=1):
                if not cell_value:
                    continue
                
                cell_value_str = str(cell_value).strip()
                parsed = self.parse_week_identifier(cell_value_str)
                
                if not parsed:
                    continue
                
                month, start_day, end_day = parsed
                
                # Check if this date falls in this week
                try:
                    year = date_obj.year
                    # Handle year boundary
                    if month < date_obj.month and date_obj.month == 12:
                        year += 1
                    elif month > date_obj.month and date_obj.month == 1:
                        year -= 1
                    
                    week_start = datetime(year, month, start_day)
                    week_end = datetime(year, month, end_day)
                    
                    # If date falls within this week range
                    if week_start <= date_obj <= week_end:
                        found_tables.append((row_idx, cell_value_str))
                            
                except ValueError:
                    # Invalid date, skip
                    continue
        
        except Exception as e:
            print(f"   ⚠️  Warning: Error searching for overlapping weeks: {e}")
        
        return found_tables
    
    def _is_rate_limit_error(self, error) -> bool:
        """Check if error is a rate limit error (429)"""
        error_str = str(error).lower()
        return '429' in error_str or 'quota exceeded' in error_str or 'rate limit' in error_str
    
    def insert_order(self, sheet_name: str, order_data: dict, retry_on_rate_limit: bool = True) -> bool:
        """Insert order into appropriate sheet and week table
        Handles overlap days by inserting into BOTH week tables with split pricing
        Automatically retries on rate limit errors
        
        Args:
            sheet_name: Name of the sheet (license plate)
            order_data: Dictionary with order data
            retry_on_rate_limit: Whether to retry on rate limit errors
            
        Returns:
            True on success, False on failure
        """
        # Validate required fields
        if not order_data.get('termin_rozladunku'):
            print(f"❌ ERROR: Missing 'termin_rozladunku' for order {order_data.get('zlecenie_nr', 'unknown')}")
            return False
        
        if not order_data.get('tablica_rejestracyjna'):
            print(f"❌ ERROR: Missing 'tablica_rejestracyjna' for order {order_data.get('zlecenie_nr', 'unknown')}")
            return False
        
        target_date = order_data['termin_rozladunku']
        
        try:
            # Get sheet by name
            try:
                sheet = self.workbook.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                print(f"❌ ERROR: Sheet '{sheet_name}' not found")
                return False
            
            # Find ALL week tables that include this date (handles overlaps)
            week_tables = self.find_overlapping_weeks(sheet, target_date)
            
            if not week_tables:
                print(f"❌ ERROR: No week table found for date {target_date} in sheet {sheet_name}")
                return False
            
            # Check if this is an overlap day (date appears in multiple weeks)
            is_overlap = len(week_tables) > 1
            
            # Get original price
            original_fracht = order_data.get('fracht')
            if original_fracht is None or original_fracht == 'storno?':
                # If no price, use as-is
                fracht_to_use = 'storno?'
                original_price = 'storno?'
            else:
                # Calculate split price (50/50 for 2 weeks, 33/33/33 for 3 weeks, etc.)
                fracht_to_use = original_fracht / len(week_tables) if is_overlap else original_fracht
                original_price = original_fracht
            
            # Track successful insertions
            success_count = 0
            
            # Try to insert into each overlapping week table
            for table_start_row, week_id in week_tables:
                # Find insertion position
                insert_row = self.find_insertion_position(sheet, table_start_row, target_date)
                
                # If table is full, skip to next one
                if insert_row is None:
                    print(f"   ⚠️  Week table ({week_id}) is full, skipping...")
                    continue
                
                # Prepare row data
                # Calculate position number (1-10) based on row
                position_number = insert_row - (table_start_row + 1)
                
                # Build row with 7 columns (A-G)
                row = [
                    position_number,  # Column A: position number (1-10)
                    target_date,  # Column B: date
                    order_data.get('miejsce_zaladunku') or '',  # Column C: loading city
                    order_data.get('miejsce_rozladunku') or '',  # Column D: unloading city
                    order_data.get('zlecenie_nr') or '',  # Column E: order number
                    fracht_to_use,  # Column F: split price (half if overlap, full if not)
                    original_price if is_overlap else '',  # Column G: original price (only for overlaps)
                ]
                
                # UPDATE the empty row (don't insert new row)
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Use update() instead of insert_row() to fill existing position
                        range_notation = f'A{insert_row}:G{insert_row}'
                        sheet.update(range_notation, [row], value_input_option='RAW')
                        
                        # Format date cell as date type
                        sheet.format(f'B{insert_row}', {
                            "numberFormat": {
                                "type": "DATE",
                                "pattern": "yyyy-mm-dd"
                            }
                        })
                        
                        # Format price cells as number
                        sheet.format(f'F{insert_row}:G{insert_row}', {
                            "numberFormat": {
                                "type": "NUMBER",
                                "pattern": "#,##0.00"
                            }
                        })
                        
                        success_count += 1
                        
                        # Show message for overlap insertions
                        if is_overlap and success_count == 1:
                            print(f"   ℹ️  Overlap day detected - inserting into {len(week_tables)} week tables (price split {100/len(week_tables):.0f}/{100/len(week_tables):.0f})")
                        
                        break  # Success, exit retry loop
                        
                    except Exception as e:
                        # Check if it's a rate limit error
                        if self._is_rate_limit_error(e) and retry_on_rate_limit and attempt < max_retries - 1:
                            wait_time = 60  # Wait 60 seconds
                            print(f"\n   ⚠️  Rate limit reached! Waiting {wait_time} seconds... ", end='', flush=True)
                            
                            # Countdown display
                            for remaining in range(wait_time, 0, -10):
                                print(f"{remaining}s... ", end='', flush=True)
                                time.sleep(10)
                            
                            print("Retrying...", end=' ', flush=True)
                            continue  # Retry
                        else:
                            # Not a rate limit error, or max retries reached
                            print(f"   ❌ Failed to insert into week {week_id}: {e}")
                            break  # Exit retry loop
            
            # Check if at least one insertion succeeded
            if success_count > 0:
                return True
            else:
                print(f"⚠️  WARNING: Could not insert order {order_data.get('zlecenie_nr', 'unknown')} into any week table")
                return False
                    
        except Exception as e:
            print(f"❌ ERROR: Failed to process order {order_data.get('zlecenie_nr', 'unknown')}: {e}")
            return False
    
    def export_grouped_orders(self, grouped_data: dict, verbose: bool = True) -> dict:
        """Export grouped orders to Google Sheets
        Automatically handles rate limiting by waiting and retrying
        
        Args:
            grouped_data: Dictionary with plate as key, list of orders as value
            verbose: Whether to print progress
            
        Returns:
            Dictionary with statistics: {'total': int, 'success': int, 'failed': int, 'missing_plate': int}
        """
        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'missing_plate': 0
        }
        
        for plate, orders in grouped_data.items():
            # Sort orders chronologically by date
            sorted_orders = sorted(
                orders,
                key=lambda x: x.get('termin_rozladunku') or '9999-99-99'
            )
            
            if verbose:
                print(f"\n📋 Processing sheet: {plate} ({len(sorted_orders)} orders)")
            
            for order in sorted_orders:
                stats['total'] += 1
                
                if not order.get('tablica_rejestracyjna'):
                    stats['missing_plate'] += 1
                    continue
                
                if verbose:
                    order_nr = order.get('zlecenie_nr', 'unknown')
                    date = order.get('termin_rozladunku', 'N/A')
                    print(f"  → Inserting {order_nr} ({date})...", end=' ', flush=True)
                
                success = self.insert_order(plate, order, retry_on_rate_limit=True)
                
                if success:
                    stats['success'] += 1
                    if verbose:
                        print("✅")
                else:
                    stats['failed'] += 1
                    if verbose:
                        print("❌")
        
        return stats
    
    def handle_no_plate_orders(self, no_plate_list: list) -> None:
        """Handle orders without license plate
        
        Args:
            no_plate_list: List of orders without tablica_rejestracyjna
        """
        if not no_plate_list:
            return
        
        print("\n⚠️  ORDERS WITHOUT LICENSE PLATE:")
        for order in no_plate_list:
            zlecenie_nr = order.get('zlecenie_nr', 'unknown')
            
            # Find other missing fields
            missing_fields = []
            required = ['termin_rozladunku', 'miejsce_zaladunku', 'miejsce_rozladunku', 'zlecenie_nr']
            for field in required:
                if not order.get(field):
                    missing_fields.append(field)
            
            missing_str = 'tablica_rejestracyjna'
            if missing_fields:
                missing_str += ', ' + ', '.join(missing_fields)
            
            print(f"⚠️  Order {zlecenie_nr} SKIPPED - Missing: {missing_str}")