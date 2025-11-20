# extractors/data_processor.py
"""Data processing and grouping module"""

import json
from collections import defaultdict
from utils.helpers import print_header, print_separator


class DataProcessor:
    """Process and group extracted data"""
    
    def group_by_plate(self, results):
        """Group results by license plate"""
        grouped = defaultdict(list)
        no_plate = []
        
        for result in results:
            plate = result.get('tablica_rejestracyjna')
            if plate:
                grouped[plate].append(result)
            else:
                no_plate.append(result)
        
        # Sort by date within each group
        for plate in grouped:
            grouped[plate].sort(key=lambda x: x.get('termin_rozladunku') or '9999-99-99')
        
        # Sort no_plate by date
        no_plate.sort(key=lambda x: x.get('termin_rozladunku') or '9999-99-99')
        
        return dict(grouped), no_plate
    
    def display_grouped_results(self, grouped, no_plate):
        """Display results grouped by plate"""
        print_header("📊 RESULTS BY LICENSE PLATE")
        
        for plate, records in sorted(grouped.items()):
            print(f"\n{'='*70}")
            print(f"🚗 TABLICA: {plate} ({len(records)} zlecenia)")
            print(f"{'='*70}")
            
            # Table header: Nr Zlecenia | Loading City | Unloading City | Data | Fracht | Plik
            print(f"{'Nr Zlecenia':<15} {'Loading City':<40} {'Unloading City':<60} {'Data':<12} {'Fracht':<10} {'Plik':<30}")
            print_separator()
            
            total_fracht = 0
            for rec in records:
                zlecenie = rec.get('zlecenie_nr', 'N/A')
                loading_city = rec.get('miejsce_zaladunku') or '—'
                unloading_city = rec.get('miejsce_rozladunku') or '—'
                date = rec.get('termin_rozladunku', 'N/A')
                fracht = rec.get('fracht', 0) or 0
                file = rec.get('source_file', 'N/A')[:28]
                
                print(f"{zlecenie:<15} {loading_city:<40} {unloading_city:<60} {date:<12} {fracht:<10.2f} {file:<30}")
                total_fracht += fracht
            
            print_separator()
            print(f"{'TOTAL:':<15} {'':<12} {total_fracht:<10.2f} EUR")
        
        # Display no plate
        if no_plate:
            print(f"\n{'='*70}")
            print(f"❌ BEZ TABLICY ({len(no_plate)} zleceń)")
            print(f"{'='*70}")
            
            for rec in no_plate:
                zlecenie = rec.get('zlecenie_nr', 'N/A')
                loading_city = rec.get('miejsce_zaladunku') or '—'
                unloading_city = rec.get('miejsce_rozladunku') or '—'
                date = rec.get('termin_rozladunku', 'N/A')
                file = rec.get('source_file', 'N/A')
                print(f"  • {zlecenie:<15} {loading_city} -> {unloading_city} | {date} - {file}")
    
    def display_summary(self, total_pdfs, successful, failed, grouped, no_plate):
        """Display processing summary"""
        print_header("📈 SUMMARY")
        print(f"Total PDFs processed: {total_pdfs}")
        print(f"✅ Successful: {successful}")
        print(f"⚠️  Incomplete: {total_pdfs - successful - failed}")
        print(f"❌ Failed: {failed}")
        print(f"\n🚗 Unique license plates: {len(grouped)}")
        print(f"❌ Documents without plate: {len(no_plate)}")
    
    def display_fracht_totals(self, grouped):
        """Display total fracht by plate"""
        print_header("💰 TOTAL FRACHT BY PLATE")
        
        # Sort by total fracht descending
        sorted_plates = sorted(
            grouped.items(),
            key=lambda x: sum(r.get('fracht', 0) or 0 for r in x[1]),
            reverse=True
        )
        
        for plate, records in sorted_plates:
            total = sum(r.get('fracht', 0) or 0 for r in records)
            count = len(records)
            avg = total / count if count > 0 else 0
            print(f"{plate:<12} : {total:>8.2f} EUR ({count} zleceń, avg: {avg:.2f} EUR)")
    
    def save_to_json(self, grouped, no_plate, summary, output_file):
        """Save results to JSON file"""
        data = {
            'summary': summary,
            'grouped_by_plate': grouped,
            'no_plate': no_plate
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_file}")