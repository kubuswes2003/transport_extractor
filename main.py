import os
from extractors.pdf_reader import PDFReader
from extractors.regex_extractor import RegexExtractor
from extractors.data_processor import DataProcessor
from utils.helpers import print_header
from config import PDFS_FOLDER, JSON_OUTPUT


class TransportExtractorApp:
    """Main application class"""
    
    def __init__(self):
        self.pdf_reader = PDFReader(PDFS_FOLDER)
        self.regex_extractor = RegexExtractor()
        self.data_processor = DataProcessor()
    
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
    
    def process_all_pdfs(self):
        """Batch mode - process all PDFs"""
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
    
    def run(self):
        """Main application loop"""
        while True:
            print_header("📄 TRANSPORT DOCUMENT EXTRACTOR")
            print("Choose option:")
            print("1. Process single PDF (interactive)")
            print("2. Process ALL PDFs (batch)")
            print("0. Exit")
            
            choice = input("\nYour choice: ").strip()
            
            if choice == '1':
                self.process_single_pdf()
                input("\nPress Enter to continue...")
            
            elif choice == '2':
                self.process_all_pdfs()
                input("\nPress Enter to continue...")
            
            elif choice == '0':
                print("\n👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice!")


if __name__ == "__main__":
    app = TransportExtractorApp()
    app.run()