# extractors/google_sheets_exporter.py
"""Google Sheets exporter - v1.6 FINAL - Kolumna A = Numer zlecenia!"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import calendar
from typing import Optional


class GoogleSheetsExporter:
    """Export extracted transport order data to Google Sheets"""
    
    def __init__(self, sheet_id: str, credentials_path: str = 'credentials.json'):
        """Initialize Google Sheets exporter"""
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
        """Parse week identifier string"""
        import re
        
        pattern = r'^(\d{1,2})\.(\d{1,2})-(\d{1,2})$'
        match = re.match(pattern, identifier.strip())
        
        if not match:
            return None
        
        try:
            month = int(match.group(1))
            start_day = int(match.group(2))
            end_day = int(match.group(3))
            
            if 1 <= month <= 12 and 1 <= start_day <= 31 and 1 <= end_day <= 31:
                return (month, start_day, end_day)
        except (ValueError, IndexError):
            return None
        
        return None
    
    def find_week_tables(self, sheet, target_date: str) -> list[int]:
        """Find ALL week table rows for a given date (może być więcej niż 1!)
        
        Returns:
            Lista row numbers gdzie data pasuje
        """
        date = datetime.strptime(target_date, '%Y-%m-%d')
        target_month = date.month
        target_day = date.day
        
        matching_rows = []
        
        try:
            all_cells = sheet.findall(r'\d+\.\d+-\d+', in_column=1)
            
            for cell in all_cells:
                cell_value = str(cell.value).strip()
                parsed = self.parse_week_identifier(cell_value)
                
                if parsed:
                    month, start_day, end_day = parsed
                    if month == target_month and start_day <= target_day <= end_day:
                        matching_rows.append(cell.row)
        except Exception as e:
            pass
        
        if matching_rows:
            return sorted(matching_rows)  # Sortuj żeby pierwsza była wcześniejsza
        
        try:
            max_rows_to_check = min(1000, sheet.row_count)
            col_a_range = sheet.range(f'A1:A{max_rows_to_check}')
            
            for cell in col_a_range:
                if not cell.value:
                    continue
                
                cell_value_str = str(cell.value).strip()
                parsed = self.parse_week_identifier(cell_value_str)
                if not parsed:
                    continue
                
                month, start_day, end_day = parsed
                
                if month == target_month and start_day <= target_day <= end_day:
                    matching_rows.append(cell.row)
            
        except Exception as e:
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
                            matching_rows.append(row_idx)
            except Exception:
                pass
        
        return sorted(list(set(matching_rows)))  # Usuń duplikaty i sortuj
    
    def find_insertion_row(self, sheet, table_start_row: int, target_date: str) -> int:
        """Find the EXACT row number where to write data
        
        LAYOUT:
        Column A = Order number (zlecenie_nr)
        Column B = Date
        Column C = Loading city
        Column D = Unloading city  
        Column E = Fracht price
        """
        data_start_row = table_start_row + 2
        
        try:
            max_check = min(data_start_row + 50, sheet.row_count)
            
            # Check column A (order numbers) to find empty row
            order_cells = sheet.range(f'A{data_start_row}:A{max_check}')
            
            for cell in order_cells:
                # If we find empty cell in column A, use this row
                if not cell.value or str(cell.value).strip() == '':
                    return cell.row
                
                # Check date in column B for chronological order
                try:
                    date_cell = sheet.cell(cell.row, 2)
                    if not date_cell.value or str(date_cell.value).strip() == '':
                        return cell.row
                        
                    existing_value = str(date_cell.value).strip()
                    if len(existing_value) == 10 and existing_value.count('-') == 2:
                        existing_date = existing_value
                    else:
                        existing_date_obj = datetime.fromisoformat(str(date_cell.value).replace('/', '-'))
                        existing_date = existing_date_obj.strftime('%Y-%m-%d')
                    
                    if target_date < existing_date:
                        return cell.row
                        
                except:
                    continue
            
            # Find last non-empty row
            for cell in reversed(order_cells):
                if cell.value and str(cell.value).strip():
                    return cell.row + 1
                    
            return data_start_row
            
        except Exception as e:
            print(f"⚠️  Warning in find_insertion_row: {e}")
            return data_start_row
    
    def insert_order(self, sheet_name: str, order_data: dict) -> bool:
        """Insert order - może wstawić do WIELU tabel jeśli data pasuje do >1 tygodnia!
        
        Przykład: data 11.16, tabele: 11.10-17 i 11.17-24
        -> Wstawi do OBU tabel z ceną podzieloną na pół
        -> W drugiej tabeli dodatkowo pełna cena w kolumnie G
        """
        if not order_data.get('termin_rozladunku'):
            print(f"❌ ERROR: Missing 'termin_rozladunku' for order {order_data.get('zlecenie_nr', 'unknown')}")
            return False
        
        if not order_data.get('tablica_rejestracyjna'):
            print(f"❌ ERROR: Missing 'tablica_rejestracyjna' for order {order_data.get('zlecenie_nr', 'unknown')}")
            return False
        
        target_date = order_data['termin_rozladunku']
        
        try:
            try:
                sheet = self.workbook.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                print(f"❌ ERROR: Sheet '{sheet_name}' not found")
                return False
            
            # Znajdź WSZYSTKIE pasujące tabele
            table_start_rows = self.find_week_tables(sheet, target_date)
            
            if not table_start_rows:
                date_obj = datetime.strptime(target_date, '%Y-%m-%d')
                print(f"\n   🔍 DEBUG: Searching for date {target_date} (month={date_obj.month}, day={date_obj.day})")
                print(f"❌ ERROR: No week table found for date {target_date} in sheet {sheet_name}")
                return False
            
            # Jeśli znaleziono więcej niż 1 tabelę
            if len(table_start_rows) > 1:
                print(f"   ℹ️  Found {len(table_start_rows)} matching week tables - will insert into ALL of them")
            
            original_fracht = order_data.get('fracht')
            
            # Wstaw do każdej pasującej tabeli
            for idx, table_start_row in enumerate(table_start_rows):
                is_first = (idx == 0)
                is_last = (idx == len(table_start_rows) - 1)
                
                target_row = self.find_insertion_row(sheet, table_start_row, target_date)
                
                # Jeśli jest więcej niż 1 tabela, dziel cenę na pół
                if len(table_start_rows) > 1:
                    fracht_value = original_fracht / 2 if original_fracht else 'storno?'
                else:
                    fracht_value = original_fracht or 'storno?'
                
                cells_to_update = [
                    # Column A: PUSTE (numer tabeli)
                    # Column B: DATA
                    gspread.Cell(target_row, 2, target_date),
                    # Column C: OD
                    gspread.Cell(target_row, 3, order_data.get('miejsce_zaladunku') or ''),
                    # Column D: DO
                    gspread.Cell(target_row, 4, order_data.get('miejsce_rozladunku') or ''),
                    # Column E: NR ZLECENIA
                    gspread.Cell(target_row, 5, order_data.get('zlecenie_nr') or ''),
                    # Column F: CENA (podzielona jeśli >1 tabela)
                    gspread.Cell(target_row, 6, fracht_value),
                ]
                
                # Jeśli było >1 tabel, dodaj pełną cenę w kolumnie G w KAŻDEJ tabeli
                if len(table_start_rows) > 1:
                    cells_to_update.append(
                        gspread.Cell(target_row, 7, original_fracht or 'storno?')
                    )
                
                try:
                    sheet.update_cells(cells_to_update, value_input_option='RAW')
                    
                    # Format date cell
                    sheet.format(f'B{target_row}', {
                        "numberFormat": {
                            "type": "DATE",
                            "pattern": "yyyy-mm-dd"
                        }
                    })
                    
                    if len(table_start_rows) > 1:
                        table_num = idx + 1
                        print(f"      ✅ Inserted into table {table_num}/{len(table_start_rows)} (row {target_row})")
                    
                except Exception as e:
                    print(f"❌ ERROR: Failed to update cells for order {order_data.get('zlecenie_nr', 'unknown')}: {e}")
                    return False
            
            return True
                    
        except Exception as e:
            print(f"❌ ERROR: Failed to process order {order_data.get('zlecenie_nr', 'unknown')}: {e}")
            return False
    
    def export_grouped_orders(self, grouped_data: dict, verbose: bool = True) -> dict:
        """Export grouped orders to Google Sheets"""
        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'missing_plate': 0
        }
        
        for plate, orders in grouped_data.items():
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
                    print(f"  → Inserting {order_nr} ({date})...", end=' ')
                
                success = self.insert_order(plate, order)
                
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
        """Handle orders without license plate"""
        if not no_plate_list:
            return
        
        print("\n⚠️  ORDERS WITHOUT LICENSE PLATE:")
        for order in no_plate_list:
            zlecenie_nr = order.get('zlecenie_nr', 'unknown')
            
            missing_fields = []
            required = ['termin_rozladunku', 'miejsce_zaladunku', 'miejsce_rozladunku', 'zlecenie_nr']
            for field in required:
                if not order.get(field):
                    missing_fields.append(field)
            
            missing_str = 'tablica_rejestracyjna'
            if missing_fields:
                missing_str += ', ' + ', '.join(missing_fields)
            
            print(f"⚠️  Order {zlecenie_nr} SKIPPED - Missing: {missing_str}")