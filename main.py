import os
import json
from extractors.pdf_reader import PDFReader
from extractors.regex_extractor import RegexExtractor
from extractors.data_processor import DataProcessor
from extractors.city_extractor import CityExtractor
from extractors.google_sheets_exporter import GoogleSheetsExporter
from database.db_manager import DatabaseManager
from utils.helpers import print_header
from config import (PDFS_FOLDER, JSON_OUTPUT, GOOGLE_SHEET_ID, CREDENTIALS_FILE,
                    ENABLE_SHEETS_EXPORT, DB_PATH, DEFAULT_EUR_PLN_RATE)


class TransportExtractorApp:
    """Main CLI application"""

    def __init__(self):
        self.pdf_reader = PDFReader(PDFS_FOLDER)
        self.regex_extractor = RegexExtractor()
        self.data_processor = DataProcessor()
        self.city_extractor = CityExtractor(use_spacy=True)
        self.sheets_exporter = None
        self._sheets_exporter_initialized = False
        self.db = DatabaseManager(DB_PATH)

    def process_single_pdf(self):
        """Interactive mode — process single PDF"""
        print_header("📄 SINGLE PDF EXTRACTION")
        pdf_files = self.pdf_reader.list_pdf_files()
        if not pdf_files:
            print("❌ No PDF files found"); return

        print(f"📁 Found {len(pdf_files)} PDF files:\n")
        for i, pf in enumerate(pdf_files, 1):
            path = os.path.join(PDFS_FOLDER, pf)
            size = self.pdf_reader.get_file_size(path)
            print(f"  {i}. {pf:<40} ({size:.1f} KB)")

        print()
        try:
            choice = int(input("Choose PDF number (0 to exit): "))
            if choice == 0: return
            if 1 <= choice <= len(pdf_files):
                pf = pdf_files[choice - 1]
                path = os.path.join(PDFS_FOLDER, pf)
                print(f"\n{'='*60}\n📄 Processing: {pf}\n{'='*60}\n")
                text = self.pdf_reader.extract_text(path)
                print(f"✅ Extracted {len(text)} characters\n")

                print_header("🔍 REGEX EXTRACTION", width=60)
                data = self.regex_extractor.extract_all_fields(text, verbose=True)
                lc, uc = self.city_extractor.extract_from_text(text)
                data['miejsce_zaladunku'] = lc
                data['miejsce_rozladunku'] = uc

                diag = self.city_extractor.ner_diagnostics()
                print_header("🧪 NER STATUS", width=60)
                for k in ('spacy_available','requested_models','loaded_models','missing_models'):
                    print(f"{k}: {diag[k]}")

                print_header("⚖️ METHOD COMPARISON", width=60)
                cmp = self.city_extractor.compare_methods(text)
                for m in ('regex','spacy','hybrid'):
                    print(f"{m:12} -> zaladunek: {cmp[m]['miejsce_zaladunku']}, rozladunek: {cmp[m]['miejsce_rozladunku']}")

                print_header("📊 RESULTS", width=60)
                for key, value in data.items():
                    print(f"{'✅' if value else '❌'} {key:<25} : {value}")
                found = sum(1 for v in data.values() if v is not None)
                print(f"\n📈 SUCCESS: {found}/{len(data)} ({100*found/len(data):.0f}%)")
            else:
                print("❌ Invalid choice!")
        except ValueError:
            print("❌ Enter a valid number!")
        except Exception as e:
            print(f"❌ Error: {e}")

    def _get_sheets_exporter(self):
        if not ENABLE_SHEETS_EXPORT: return None
        if not self._sheets_exporter_initialized:
            try:
                self.sheets_exporter = GoogleSheetsExporter(GOOGLE_SHEET_ID, CREDENTIALS_FILE)
            except Exception as e:
                print(f"❌ Sheets init failed: {e}")
                self.sheets_exporter = None
            self._sheets_exporter_initialized = True
        return self.sheets_exporter

    def export_to_sheets(self):
        """Export last results to Google Sheets"""
        print_header("📊 EXPORT TO GOOGLE SHEETS")
        exporter = self._get_sheets_exporter()
        if not exporter:
            print("❌ Sheets export unavailable"); return
        if not os.path.exists(JSON_OUTPUT):
            print(f"❌ No results ({JSON_OUTPUT}). Process PDFs first."); return
        try:
            with open(JSON_OUTPUT, 'r', encoding='utf-8') as f:
                data = json.load(f)
            grouped = data.get('grouped_by_plate', {})
            no_plate = data.get('no_plate', [])
            if not grouped and not no_plate:
                print("❌ No data to export"); return
            print(f"📋 {len(grouped)} sheets, {len(no_plate)} no-plate\n")
            stats = exporter.export_grouped_orders(grouped, verbose=True)
            exporter.handle_no_plate_orders(no_plate)
            print_header("📈 EXPORT SUMMARY")
            print(f"Total: {stats['total']}")
            print(f"✅ Success: {stats['success']}")
            print(f"❌ Failed: {stats['failed']}")
            if stats['missing_plate'] > 0:
                print(f"⚠️  Missing plate: {stats['missing_plate']}")
        except Exception as e:
            print(f"❌ Error: {e}")

    def process_all_pdfs(self, export_to_sheets: bool = False):
        """Batch mode — process all PDFs and save to SQLite"""
        print_header("🔥 BATCH PROCESSING")
        pdf_files = self.pdf_reader.list_pdf_files()
        if not pdf_files:
            print("❌ No PDF files found"); return
        print(f"📁 Found {len(pdf_files)} PDF files\n")
        confirm = input(f"Process all {len(pdf_files)} PDFs? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Cancelled"); return

        all_results, successful, failed = [], 0, 0
        print_header("⏳ PROCESSING...")
        for i, pf in enumerate(pdf_files, 1):
            path = os.path.join(PDFS_FOLDER, pf)
            print(f"[{i}/{len(pdf_files)}] {pf:<45} ", end="")
            try:
                text = self.pdf_reader.extract_text(path)
                data = self.regex_extractor.extract_all_fields(text, verbose=False)
                lc, uc = self.city_extractor.extract_from_text(text)
                data['miejsce_zaladunku'] = lc
                data['miejsce_rozladunku'] = uc
                data['source_file'] = pf
                missing = [k for k, v in data.items() if v is None and k != 'source_file']
                if missing: print(f"⚠️  ({len(missing)} missing)")
                else: print("✅"); successful += 1
                all_results.append(data)
            except Exception as e:
                print(f"❌ {e}"); failed += 1

        grouped, no_plate = self.data_processor.group_by_plate(all_results)
        self.data_processor.display_grouped_results(grouped, no_plate)
        self.data_processor.display_summary(len(pdf_files), successful, failed, grouped, no_plate)
        self.data_processor.display_fracht_totals(grouped)

        # Save to JSON (legacy)
        summary = {'total_pdfs': len(pdf_files), 'successful': successful,
                    'failed': failed, 'unique_plates': len(grouped)}
        self.data_processor.save_to_json(grouped, no_plate, summary, JSON_OUTPUT)

        # Save to SQLite
        print_header("💾 SAVING TO DATABASE")
        saved, dupes = 0, 0
        for plate, orders in grouped.items():
            truck_id, _ = self.db.add_truck(plate)
            for order in orders:
                dt = order.get('termin_rozladunku', '')
                wt_id = self.db.find_or_create_week_table(truck_id, dt, DEFAULT_EUR_PLN_RATE)
                ok, msg = self.db.add_order(wt_id, {
                    'zlecenie_nr': order.get('zlecenie_nr'),
                    'termin_rozladunku': dt,
                    'miejsce_zaladunku': order.get('miejsce_zaladunku'),
                    'miejsce_rozladunku': order.get('miejsce_rozladunku'),
                    'fracht_eur': order.get('fracht'),
                    'source_file': order.get('source_file'),
                })
                if ok: saved += 1
                elif msg == "duplicate":
                    dupes += 1
                    print(f"⚠️  {order.get('zlecenie_nr', '?')} — duplicate, skipped")
                else:
                    print(f"❌ {order.get('zlecenie_nr', '?')}: {msg}")
        print(f"\n📈 Saved: {saved} | Duplicates: {dupes}")

        if export_to_sheets:
            self.export_to_sheets()

    def view_database(self):
        """View database contents in CLI"""
        print_header("📋 DATABASE CONTENTS")
        trucks = self.db.get_all_trucks()
        if not trucks:
            print("Database is empty. Process PDFs first."); return
        print(f"Found {len(trucks)} trucks:\n")
        for t in trucks:
            print(f"\n🚗 {t['plate']} (driver: {t.get('driver_name', '—')})")
            weeks = self.db.get_week_tables(t['id'])
            for w in weeks:
                s = self.db.get_week_summary(w['id'])
                print(f"  📅 Week {w['week_identifier']}: {s['order_count']} orders, "
                      f"SUMA: {s['suma_eur']:.2f}€, STAWKA: {s['stawka_eur']:.2f}€/km, "
                      f"KM: {s['km_total']}")
                orders = self.db.get_orders_by_week(w['id'])
                for o in orders:
                    f = o['fracht_eur']
                    fstr = f"{f:.2f}€" if f else "storno?"
                    print(f"    {o['row_number']}. {o['termin_rozladunku'] or '?'} | "
                          f"{o['miejsce_zaladunku'] or '—'} → {o['miejsce_rozladunku'] or '—'} | "
                          f"{o['zlecenie_nr'] or '?'} | {fstr}")

    def database_stats(self):
        """Show database statistics"""
        print_header("📊 DATABASE STATISTICS")
        st = self.db.get_statistics()
        print(f"Total orders:  {st['total_orders']}")
        print(f"Unique trucks: {st['unique_plates']}")
        print(f"Total fracht:  {st['total_fracht_eur']:.2f} EUR")
        print(f"Avg fracht:    {st['avg_fracht_eur']:.2f} EUR")
        dr = st['date_range']
        print(f"Date range:    {dr.get('min_date','?')} → {dr.get('max_date','?')}")
        print(f"\nMissing fields:")
        for f, c in st['missing_fields'].items():
            print(f"  {f}: {c}")
        print(f"\nFracht per truck:")
        for p, d in st['fracht_per_plate'].items():
            print(f"  {p}: {d['total_fracht']:.2f}€ ({d['order_count']} orders, avg {d['avg_fracht']:.2f}€)")

    def run(self):
        """Main application loop"""
        while True:
            print_header("📄 TRANSPORT DOCUMENT EXTRACTOR")
            print("Choose option:")
            print("1. Process single PDF (interactive)")
            print("2. Process ALL PDFs (batch → SQLite)")
            print("3. Export to Google Sheets (from last JSON)")
            print("4. Process ALL + Export to Sheets")
            print("5. View database")
            print("6. Database statistics")
            print("0. Exit")

            choice = input("\nYour choice: ").strip()
            if choice == '1':
                self.process_single_pdf()
            elif choice == '2':
                self.process_all_pdfs()
            elif choice == '3':
                self.export_to_sheets()
            elif choice == '4':
                self.process_all_pdfs(export_to_sheets=True)
            elif choice == '5':
                self.view_database()
            elif choice == '6':
                self.database_stats()
            elif choice == '0':
                self.db.close()
                print("\n👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice!")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    app = TransportExtractorApp()
    app.run()