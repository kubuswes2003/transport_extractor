import os
import json
from extractors.pdf_reader import PDFReader
from extractors.regex_extractor import RegexExtractor
from extractors.data_processor import DataProcessor
from extractors.city_extractor import CityExtractor
from extractors.google_sheets_exporter import GoogleSheetsExporter
from utils.helpers import print_header
from config import PDFS_FOLDER, JSON_OUTPUT, GOOGLE_SHEET_ID, CREDENTIALS_FILE, ENABLE_SHEETS_EXPORT


class TransportExtractorApp:
    """Main application class"""
    
    def __init__(self):
        self.pdf_reader = PDFReader(PDFS_FOLDER)
        self.regex_extractor = RegexExtractor()
        self.data_processor = DataProcessor()
        self.city_extractor = CityExtractor(use_spacy=True)
        self.sheets_exporter = None  # Lazy initialization
        self._sheets_exporter_initialized = False
    
    def process_single_pdf(self):
        """Interactive mode - process single PDF"""
        print_header("📄 SINGLE PDF EXTRACTION")
        
        pdf_files = self.pdf_reader.list_pdf_files()
        
        if not pdf_files:
            print("❌ No PDF files found")
            return
        
        print(f"📁 Found {len(pdf_files)} PDF files:\n")
        
        for i, pdf_file in enumerate(pdf_files, 1):
            pdf_path = os.path.join(PDFS_FOLDER, pdf_file)
            size = self.pdf_reader.get_file_size(pdf_path)
            print(f"  {i}. {pdf_file:<40} ({size:.1f} KB)")
        
        print()
        try:
            choice = int(input("Choose PDF number (0 to exit): "))
            
            if choice == 0:
                return
            
            if 1 <= choice <= len(pdf_files):
                selected_pdf = pdf_files[choice - 1]
                pdf_path = os.path.join(PDFS_FOLDER, selected_pdf)
                
                print(f"\n{'='*60}")
                print(f"📄 Processing: {selected_pdf}")
                print(f"{'='*60}\n")
                
                # Extract text
                print("⏳ Extracting text...")
                text = self.pdf_reader.extract_text(pdf_path)
                print(f"✅ Extracted {len(text)} characters\n")
                
                # Extract data
                print("⏳ Extracting data with REGEX...\n")
                print_header("🔍 REGEX EXTRACTION", width=60)
                
                data = self.regex_extractor.extract_all_fields(text, verbose=True)
                # Extract cities
                loading_city, unloading_city = self.city_extractor.extract_from_text(text)
                data['miejsce_zaladunku'] = loading_city
                data['miejsce_rozladunku'] = unloading_city

                # NER diagnostics
                diag = self.city_extractor.ner_diagnostics()
                print_header("🧪 NER STATUS", width=60)
                print(f"spacy_available: {diag['spacy_available']}")
                print(f"requested_models: {diag['requested_models']}")
                print(f"loaded_models: {diag['loaded_models']}")
                print(f"missing_models: {diag['missing_models']}")

                # Compare methods (regex vs spaCy vs hybrid)
                print_header("⚖️ METHOD COMPARISON", width=60)
                cmp = self.city_extractor.compare_methods(text)
                print(f"regex       -> zaladunek: {cmp['regex']['miejsce_zaladunku']}, rozladunek: {cmp['regex']['miejsce_rozladunku']}")
                print(f"spacy       -> zaladunek: {cmp['spacy']['miejsce_zaladunku']}, rozladunek: {cmp['spacy']['miejsce_rozladunku']}")
                print(f"hybrid used -> zaladunek: {cmp['hybrid']['miejsce_zaladunku']}, rozladunek: {cmp['hybrid']['miejsce_rozladunku']}")
                
                # Display results
                print_header("📊 RESULTS", width=60)
                for key, value in data.items():
                    status = "✅" if value is not None else "❌"
                    print(f"{status} {key:<25} : {value}")
                
                found = sum(1 for v in data.values() if v is not None)
                total = len(data)
                print(f"\n📈 SUCCESS: {found}/{total} ({100*found/total:.0f}%)")
            
            else:
                print("❌ Invalid choice!")
        
        except ValueError:
            print("❌ Enter a valid number!")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _get_sheets_exporter(self):
        """Get sheets exporter with lazy initialization"""
        if not ENABLE_SHEETS_EXPORT:
            return None
        
        if not self._sheets_exporter_initialized:
            try:
                self.sheets_exporter = GoogleSheetsExporter(GOOGLE_SHEET_ID, CREDENTIALS_FILE)
                self._sheets_exporter_initialized = True
            except FileNotFoundError as e:
                print(f"❌ {e}")
                print("   Google Sheets export will be unavailable for this session.")
                self.sheets_exporter = None
                self._sheets_exporter_initialized = True
            except Exception as e:
                print(f"❌ Failed to initialize Google Sheets exporter: {e}")
                self.sheets_exporter = None
                self._sheets_exporter_initialized = True
        
        return self.sheets_exporter
    
    def export_to_sheets(self):
        """Export last processing results to Google Sheets"""
        print_header("📊 EXPORT TO GOOGLE SHEETS")
        
        sheets_exporter = self._get_sheets_exporter()
        if not sheets_exporter:
            if not ENABLE_SHEETS_EXPORT:
                print("❌ Google Sheets export is disabled (ENABLE_SHEETS_EXPORT = False)")
            return
        
        # Load data from JSON file
        if not os.path.exists(JSON_OUTPUT):
            print(f"❌ No extraction results found ({JSON_OUTPUT})")
            print("   Please process PDFs first (option 2 or 4)")
            return
        
        try:
            with open(JSON_OUTPUT, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            grouped_by_plate = data.get('grouped_by_plate', {})
            no_plate = data.get('no_plate', [])
            
            if not grouped_by_plate and not no_plate:
                print("❌ No data to export")
                return
            
            print(f"📋 Found {len(grouped_by_plate)} sheets and {len(no_plate)} orders without plate\n")
            
            # Export grouped orders
            stats = sheets_exporter.export_grouped_orders(grouped_by_plate, verbose=True)
            
            # Handle no plate orders
            sheets_exporter.handle_no_plate_orders(no_plate)
            
            # Display summary
            print_header("📈 EXPORT SUMMARY")
            print(f"Total orders: {stats['total']}")
            print(f"✅ Successfully exported: {stats['success']}")
            print(f"❌ Failed: {stats['failed']}")
            if stats['missing_plate'] > 0:
                print(f"⚠️  Missing plate: {stats['missing_plate']}")
            
        except Exception as e:
            print(f"❌ Error exporting to Google Sheets: {e}")
    
    def process_all_pdfs(self, export_to_sheets: bool = False):
        """Batch mode - process all PDFs
        
        Args:
            export_to_sheets: Whether to export to Google Sheets after processing
        """
        print_header("🔥 BATCH PROCESSING")
        
        pdf_files = self.pdf_reader.list_pdf_files()
        
        if not pdf_files:
            print("❌ No PDF files found")
            return
        
        print(f"📁 Found {len(pdf_files)} PDF files\n")
        
        confirm = input(f"Process all {len(pdf_files)} PDFs? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Cancelled")
            return
        
        all_results = []
        successful = 0
        failed = 0
        
        print_header("⏳ PROCESSING...")
        
        for i, pdf_file in enumerate(pdf_files, 1):
            pdf_path = os.path.join(PDFS_FOLDER, pdf_file)
            
            print(f"[{i}/{len(pdf_files)}] {pdf_file:<45} ", end="")
            
            try:
                # Extract text
                text = self.pdf_reader.extract_text(pdf_path)
                
                # Extract data
                data = self.regex_extractor.extract_all_fields(text, verbose=False)
                # Cities from full text
                loading_city, unloading_city = self.city_extractor.extract_from_text(text)
                data['miejsce_zaladunku'] = loading_city
                data['miejsce_rozladunku'] = unloading_city
                data['source_file'] = pdf_file
                
                # Check completeness
                missing = [k for k, v in data.items() if v is None and k != 'source_file']
                
                if missing:
                    print(f"⚠️  ({len(missing)} missing)")
                else:
                    print("✅")
                    successful += 1
                
                all_results.append(data)
                
            except Exception as e:
                print(f"❌ ERROR: {e}")
                failed += 1
        
        # Group and display results
        grouped, no_plate = self.data_processor.group_by_plate(all_results)
        self.data_processor.display_grouped_results(grouped, no_plate)
        
        # Display summary
        self.data_processor.display_summary(
            len(pdf_files), successful, failed, grouped, no_plate
        )
        
        # Display fracht totals
        self.data_processor.display_fracht_totals(grouped)
        
        # Save to JSON
        summary = {
            'total_pdfs': len(pdf_files),
            'successful': successful,
            'failed': failed,
            'unique_plates': len(grouped)
        }
        self.data_processor.save_to_json(grouped, no_plate, summary, JSON_OUTPUT)
        
        # Export to Google Sheets if requested
        if export_to_sheets:
            self.export_to_sheets()
    
    def run(self):
        """Main application loop"""
        while True:
            print_header("📄 TRANSPORT DOCUMENT EXTRACTOR")
            print("Choose option:")
            print("1. Process single PDF (interactive)")
            print("2. Process ALL PDFs (batch)")
            print("3. Export to Google Sheets (from last processing)")
            print("4. Process ALL PDFs + Export to Sheets")
            print("0. Exit")
            
            choice = input("\nYour choice: ").strip()
            
            if choice == '1':
                self.process_single_pdf()
                input("\nPress Enter to continue...")
            
            elif choice == '2':
                self.process_all_pdfs()
                input("\nPress Enter to continue...")
            
            elif choice == '3':
                self.export_to_sheets()
                input("\nPress Enter to continue...")
            
            elif choice == '4':
                self.process_all_pdfs(export_to_sheets=True)
                input("\nPress Enter to continue...")
            
            elif choice == '0':
                print("\n👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice!")


if __name__ == "__main__":
    app = TransportExtractorApp()
    app.run()