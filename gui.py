#!/usr/bin/env python3
# gui.py
"""
Transport Document Processor - GUI Application
Cross-platform desktop application for processing transport PDFs
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Import existing modules
from extractors.pdf_reader import PDFReader
from extractors.regex_extractor import RegexExtractor
from extractors.data_processor import DataProcessor
from extractors.city_extractor import CityExtractor
from extractors.google_sheets_exporter import GoogleSheetsExporter
from config import GOOGLE_SHEET_ID, CREDENTIALS_FILE, ENABLE_SHEETS_EXPORT


class TransportGUI:
    """Main GUI Application"""
    
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Transport Document Processor")
        self.window.geometry("1100x750")  # Bigger window for bigger buttons
        self.window.resizable(True, True)
        
        # Colors
        self.BG_COLOR = "#f5f5f5"
        self.PRIMARY = "#2196F3"
        self.SUCCESS = "#4CAF50"
        self.ERROR = "#f44336"
        self.WARNING = "#FF9800"
        
        # State
        self.processing = False
        self.stop_requested = False
        self.current_folder = self.load_last_folder()
        
        # Components
        self.pdf_reader = None
        self.regex_extractor = RegexExtractor()
        self.data_processor = DataProcessor()
        self.city_extractor = CityExtractor(use_spacy=True)
        self.sheets_exporter = None
        
        # Setup UI
        self.setup_ui()
        
        # Check credentials
        self.check_credentials()
        
    def setup_ui(self):
        """Build the user interface"""
        
        # Configure main window
        self.window.configure(bg=self.BG_COLOR)
        
        # ==================== HEADER ====================
        header_frame = tk.Frame(self.window, bg=self.PRIMARY, height=80)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(
            header_frame,
            text="🚚 Transport Document Processor",
            font=("Arial", 20, "bold"),
            bg=self.PRIMARY,
            fg="white"
        )
        title_label.pack(pady=15)
        
        subtitle = tk.Label(
            header_frame,
            text="Extract data from PDFs and export to Google Sheets",
            font=("Arial", 10),
            bg=self.PRIMARY,
            fg="white"
        )
        subtitle.pack()
        
        # ==================== INPUT FRAME ====================
        input_frame = tk.LabelFrame(
            self.window,
            text="📁 PDF Folder Selection",
            font=("Arial", 11, "bold"),
            bg=self.BG_COLOR,
            padx=20,
            pady=15
        )
        input_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Folder path
        path_frame = tk.Frame(input_frame, bg=self.BG_COLOR)
        path_frame.pack(fill=tk.X)
        
        self.folder_var = tk.StringVar(value=self.current_folder or "No folder selected")
        folder_entry = tk.Entry(
            path_frame,
            textvariable=self.folder_var,
            font=("Arial", 12),
            state="readonly",
            width=60
        )
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        browse_btn = tk.Button(
            path_frame,
            text="📂 Browse Folder",
            command=self.browse_folder,
            font=("Arial", 14, "bold"),
            bg=self.PRIMARY,
            fg="white",
            width=15,
            height=3,
            relief=tk.RAISED,
            bd=5,
            activebackground="#1976D2"
        )
        browse_btn.pack(side=tk.LEFT, padx=5)
        
        # PDF List Preview
        self.pdf_list_frame = tk.Frame(input_frame, bg=self.BG_COLOR)
        self.pdf_list_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.pdf_count_label = tk.Label(
            self.pdf_list_frame,
            text="No PDFs found",
            font=("Arial", 11),
            bg=self.BG_COLOR,
            fg="#666"
        )
        self.pdf_count_label.pack(anchor=tk.W)
        
        # ==================== ACTION FRAME ====================
        action_frame = tk.Frame(self.window, bg=self.BG_COLOR)
        action_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Process button (BIGGEST - most important!)
        self.process_btn = tk.Button(
            action_frame,
            text="▶️  PROCESS & EXPORT",
            command=self.confirm_and_process,
            font=("Arial", 14, "bold"),
            bg=self.SUCCESS,
            fg="white",
            width=22,
            height=3,
            relief=tk.RAISED,
            bd=6,
            activebackground="#45a049"
        )
        self.process_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Process ONLY button (without export)
        self.process_only_btn = tk.Button(
            action_frame,
            text="📄 PROCESS ONLY",
            command=self.confirm_and_process_only,
            font=("Arial", 14, "bold"),
            bg=self.WARNING,
            fg="white",
            width=18,
            height=3,
            relief=tk.RAISED,
            bd=6,
            activebackground="#ff9800"
        )
        self.process_only_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Stop button
        self.stop_btn = tk.Button(
            action_frame,
            text="⏹️  STOP",
            command=self.stop_processing,
            font=("Arial", 16, "bold"),
            bg=self.ERROR,
            fg="white",
            width=10,
            height=3,
            relief=tk.RAISED,
            bd=6,
            activebackground="#d32f2f",
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Open Sheets button
        self.sheets_btn = tk.Button(
            action_frame,
            text="🔗 Open Google Sheets",
            command=self.open_google_sheets,
            font=("Arial", 14, "bold"),
            bg="white",
            fg=self.PRIMARY,
            width=20,
            height=3,
            relief=tk.RAISED,
            bd=5,
            activebackground="#E3F2FD"
        )
        self.sheets_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Help button
        help_btn = tk.Button(
            action_frame,
            text="❓ Help",
            command=self.show_help,
            font=("Arial", 14, "bold"),
            bg="white",
            fg="#666",
            width=12,
            height=3,
            relief=tk.RAISED,
            bd=5,
            activebackground="#F5F5F5"
        )
        help_btn.pack(side=tk.RIGHT)
        
        # ==================== PROGRESS FRAME ====================
        progress_frame = tk.LabelFrame(
            self.window,
            text="📊 Progress",
            font=("Arial", 11, "bold"),
            bg=self.BG_COLOR,
            padx=15,
            pady=10
        )
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='indeterminate',
            length=800
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Log text area (with proper scaling)
        log_frame = tk.Frame(progress_frame, bg=self.BG_COLOR)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 10),
            wrap=tk.WORD,
            height=15,
            bg="white",
            fg="black",
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure text tags for colors
        self.log_text.tag_config("success", foreground=self.SUCCESS)
        self.log_text.tag_config("error", foreground=self.ERROR)
        self.log_text.tag_config("warning", foreground=self.WARNING)
        self.log_text.tag_config("info", foreground=self.PRIMARY)
        self.log_text.tag_config("bold", font=("Consolas", 9, "bold"))
        
        # ==================== SUMMARY FRAME ====================
        self.summary_frame = tk.Frame(self.window, bg=self.BG_COLOR)
        self.summary_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        self.summary_label = tk.Label(
            self.summary_frame,
            text="Ready to process PDFs",
            font=("Arial", 12, "bold"),
            bg=self.BG_COLOR,
            fg="#666"
        )
        self.summary_label.pack()
        
        # ==================== FOOTER ====================
        footer = tk.Label(
            self.window,
            text="Made with ❤️ for Transport Team | v1.0",
            font=("Arial", 8),
            bg=self.BG_COLOR,
            fg="#999"
        )
        footer.pack(pady=5)
        
        # Initial message
        self.log("Welcome! 👋", "info")
        self.log("Select a folder with PDF files to begin.", "info")
        self.log("")
        
        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()
        
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for common actions"""
        # Cmd on Mac, Ctrl on Windows/Linux
        modifier = "Command" if sys.platform == "darwin" else "Control"
        
        # Cmd/Ctrl + O: Browse folder
        self.window.bind(f"<{modifier}-o>", lambda e: self.browse_folder())
        self.window.bind(f"<{modifier}-O>", lambda e: self.browse_folder())
        
        # Cmd/Ctrl + P: Process
        self.window.bind(f"<{modifier}-p>", lambda e: self.confirm_and_process() if not self.processing else None)
        self.window.bind(f"<{modifier}-P>", lambda e: self.confirm_and_process() if not self.processing else None)
        
        # Cmd/Ctrl + S: Open Sheets
        self.window.bind(f"<{modifier}-s>", lambda e: self.open_google_sheets())
        self.window.bind(f"<{modifier}-S>", lambda e: self.open_google_sheets())
        
        # Cmd/Ctrl + H: Help
        self.window.bind(f"<{modifier}-h>", lambda e: self.show_help())
        self.window.bind(f"<{modifier}-H>", lambda e: self.show_help())
        
        # Escape: Stop processing
        self.window.bind("<Escape>", lambda e: self.stop_processing() if self.processing else None)
        
        # Show shortcuts hint
        self.log("💡 Keyboard shortcuts:", "info")
        shortcut_key = "Cmd" if sys.platform == "darwin" else "Ctrl"
        self.log(f"   {shortcut_key}+O: Browse folder", "info")
        self.log(f"   {shortcut_key}+P: Process", "info")
        self.log(f"   {shortcut_key}+S: Open Sheets", "info")
        self.log(f"   {shortcut_key}+H: Help", "info")
        self.log(f"   Escape: Stop", "info")
        self.log("")
        
    def browse_folder(self):
        """Open folder selection dialog"""
        initial_dir = self.current_folder if self.current_folder and os.path.exists(self.current_folder) else os.path.expanduser("~")
        
        folder = filedialog.askdirectory(
            title="Select Folder with PDF Files",
            initialdir=initial_dir
        )
        
        if folder:
            self.current_folder = folder
            self.folder_var.set(folder)
            self.save_last_folder(folder)
            self.scan_pdfs()
            
    def scan_pdfs(self):
        """Scan selected folder for PDF files"""
        if not self.current_folder:
            return
            
        try:
            pdf_files = [f for f in os.listdir(self.current_folder) if f.lower().endswith('.pdf')]
            count = len(pdf_files)
            
            if count == 0:
                self.pdf_count_label.config(
                    text="❌ No PDF files found in this folder",
                    fg=self.ERROR
                )
                self.process_btn.config(state=tk.DISABLED)
            else:
                self.pdf_count_label.config(
                    text=f"✅ Found {count} PDF file{'s' if count != 1 else ''} ready to process",
                    fg=self.SUCCESS
                )
                self.process_btn.config(state=tk.NORMAL)
                
                # Show first few files
                preview = ", ".join(pdf_files[:3])
                if count > 3:
                    preview += f" ... (+{count-3} more)"
                self.log(f"📄 Files: {preview}", "info")
                
        except Exception as e:
            self.log(f"❌ Error scanning folder: {e}", "error")
            
    def confirm_and_process(self):
        """Show confirmation dialog before processing"""
        if not self.current_folder:
            messagebox.showwarning("No Folder", "Please select a folder with PDF files first!")
            return
            
        try:
            pdf_files = [f for f in os.listdir(self.current_folder) if f.lower().endswith('.pdf')]
            count = len(pdf_files)
            
            if count == 0:
                messagebox.showwarning("No PDFs", "No PDF files found in the selected folder!")
                return
                
            # Confirmation dialog
            message = f"Process {count} PDF file{'s' if count != 1 else ''}?\n\n"
            message += f"Folder: {os.path.basename(self.current_folder)}\n"
            message += f"Export to: Google Sheets\n\n"
            message += "This may take a few minutes..."
            
            result = messagebox.askyesno(
                "Confirm Processing",
                message,
                icon='question'
            )
            
            if result:
                self.start_processing()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan folder:\n{e}")
    
    def confirm_and_process_only(self):
        """Show confirmation dialog for processing WITHOUT export to Sheets"""
        if not self.current_folder:
            messagebox.showwarning("No Folder", "Please select a folder with PDF files first!")
            return
            
        try:
            pdf_files = [f for f in os.listdir(self.current_folder) if f.lower().endswith('.pdf')]
            count = len(pdf_files)
            
            if count == 0:
                messagebox.showwarning("No PDFs", "No PDF files found in the selected folder!")
                return
                
            # Confirmation dialog
            message = f"Process {count} PDF file{'s' if count != 1 else ''}?\n\n"
            message += f"Folder: {os.path.basename(self.current_folder)}\n"
            message += f"Action: Extract data ONLY (no Google Sheets export)\n\n"
            message += "Results will be saved to JSON file.\n"
            message += "This may take a few minutes..."
            
            result = messagebox.askyesno(
                "Confirm Processing (No Export)",
                message,
                icon='question'
            )
            
            if result:
                self.start_processing(export_to_sheets=False)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan folder:\n{e}")
            
    def start_processing(self, export_to_sheets=True):
        """Start processing in a separate thread
        
        Args:
            export_to_sheets: If True, export to Google Sheets after processing
        """
        self.processing = True
        self.stop_requested = False
        self.export_to_sheets = export_to_sheets  # Store for use in processing thread
        
        # Update UI
        self.process_btn.config(state=tk.DISABLED)
        self.process_only_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_bar.start(10)
        
        # Clear log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # Start processing thread
        thread = threading.Thread(target=self.process_pdfs, daemon=True)
        thread.start()
        
    def stop_processing(self):
        """Request to stop processing"""
        self.stop_requested = True
        self.log("⏹️  Stop requested... finishing current operation", "warning")
        self.stop_btn.config(state=tk.DISABLED)
        
    def process_pdfs(self):
        """Main processing logic (runs in thread)"""
        try:
            self.log("="*70, "bold")
            self.log("🚀 STARTING PROCESSING", "info")
            self.log("="*70, "bold")
            self.log("")
            
            # Initialize components
            pdf_reader = PDFReader(self.current_folder)
            pdf_files = pdf_reader.list_pdf_files()
            
            if not pdf_files:
                self.log("❌ No PDF files found!", "error")
                return
                
            self.log(f"📁 Found {len(pdf_files)} PDF files", "info")
            self.log("")
            
            all_results = []
            successful = 0
            failed = 0
            
            # Process each PDF
            for i, pdf_file in enumerate(pdf_files, 1):
                if self.stop_requested:
                    self.log("", "")
                    self.log("⏹️  Processing stopped by user", "warning")
                    break
                    
                pdf_path = os.path.join(self.current_folder, pdf_file)
                
                self.log(f"[{i}/{len(pdf_files)}] {pdf_file:<45} ", "info")
                
                try:
                    # Extract text
                    text = pdf_reader.extract_text(pdf_path)
                    
                    # Extract data (order, date, plate, fracht)
                    data = self.regex_extractor.extract_all_fields(text, verbose=False)
                    
                    # Extract cities using city_extractor (always!)
                    loading_city, unloading_city = self.city_extractor.extract_from_text(text)
                    data['miejsce_zaladunku'] = loading_city
                    data['miejsce_rozladunku'] = unloading_city
                    
                    data['source_file'] = pdf_file
                    
                    # Check completeness
                    missing = [k for k, v in data.items() if v is None and k != 'source_file']
                    
                    if missing:
                        self.log(f"   ⚠️  Missing: {', '.join(missing)}", "warning")
                    else:
                        self.log(f"   ✅ Complete", "success")
                        successful += 1
                    
                    all_results.append(data)
                    
                except Exception as e:
                    self.log(f"   ❌ ERROR: {e}", "error")
                    failed += 1
                    
            if self.stop_requested:
                self.finish_processing(None)
                return
                
            # Group results
            self.log("")
            self.log("="*70, "bold")
            self.log("📊 GROUPING BY LICENSE PLATE", "info")
            self.log("="*70, "bold")
            
            grouped, no_plate = self.data_processor.group_by_plate(all_results)
            
            self.log(f"✅ Unique plates: {len(grouped)}", "success")
            self.log(f"⚠️  Without plate: {len(no_plate)}", "warning")
            self.log("")
            
            # Display grouped results in GUI
            self.log("="*70, "bold")
            self.log("📋 EXTRACTED DATA BY LICENSE PLATE", "info")
            self.log("="*70, "bold")
            self.log("")
            
            for plate, orders in sorted(grouped.items()):
                self.log(f"🚗 {plate} ({len(orders)} orders):", "info")
                
                total_fracht = 0
                for order in orders:
                    zlecenie = order.get('zlecenie_nr', 'N/A')
                    date = order.get('termin_rozladunku', 'N/A')
                    loading = order.get('miejsce_zaladunku', '—')
                    unloading = order.get('miejsce_rozladunku', '—')
                    fracht = order.get('fracht', 0) or 0
                    
                    self.log(f"  • {zlecenie} | {date} | {loading} → {unloading} | {fracht} EUR", "info")
                    total_fracht += fracht
                
                self.log(f"  💰 TOTAL: {total_fracht:.2f} EUR", "success")
                self.log("")
            
            # Show orders without plate
            if no_plate:
                self.log("⚠️  ORDERS WITHOUT LICENSE PLATE:", "warning")
                for order in no_plate:
                    zlecenie = order.get('zlecenie_nr', 'N/A')
                    date = order.get('termin_rozladunku', 'N/A')
                    loading = order.get('miejsce_zaladunku', '—')
                    unloading = order.get('miejsce_rozladunku', '—')
                    self.log(f"  • {zlecenie} | {date} | {loading} → {unloading}", "warning")
                self.log("")
            
            # Export to Google Sheets (ONLY if requested!)
            if ENABLE_SHEETS_EXPORT and self.export_to_sheets:
                self.log("="*70, "bold")
                self.log("📤 EXPORTING TO GOOGLE SHEETS", "info")
                self.log("="*70, "bold")
                self.log("")
                
                try:
                    if not self.sheets_exporter:
                        self.sheets_exporter = GoogleSheetsExporter(GOOGLE_SHEET_ID, CREDENTIALS_FILE)
                    
                    # Export orders (only once!)
                    success_count = 0
                    failed_count = 0
                    
                    for plate, orders in grouped.items():
                        # IMPORTANT: Sort orders by date BEFORE inserting!
                        sorted_orders = sorted(
                            orders, 
                            key=lambda x: x.get('termin_rozladunku') or '9999-99-99'
                        )
                        
                        self.log(f"📋 {plate} ({len(sorted_orders)} orders):", "info")
                        for order in sorted_orders:
                            order_nr = order.get('zlecenie_nr', 'unknown')
                            date = order.get('termin_rozladunku', 'N/A')
                            
                            # Insert order (ONLY ONCE)
                            success = self.sheets_exporter.insert_order(plate, order)
                            
                            if success:
                                self.log(f"  → {order_nr} ({date})... ✅", "success")
                                success_count += 1
                            else:
                                self.log(f"  → {order_nr} ({date})... ❌ FAILED", "error")
                                # Error details are already printed by insert_order
                                failed_count += 1
                    
                    # Create stats
                    stats = {
                        'total': success_count + failed_count,
                        'success': success_count,
                        'failed': failed_count
                    }
                    
                    # Handle no plate orders
                    if no_plate:
                        self.log("")
                        self.log("⚠️  ORDERS WITHOUT LICENSE PLATE:", "warning")
                        for order in no_plate:
                            zlecenie_nr = order.get('zlecenie_nr', 'unknown')
                            self.log(f"⚠️  Order {zlecenie_nr} SKIPPED", "warning")
                    
                    self.log("")
                    self.log("="*70, "bold")
                    self.log("📈 EXPORT SUMMARY", "info")
                    self.log("="*70, "bold")
                    self.log(f"Total orders: {stats['total']}", "info")
                    self.log(f"✅ Successfully exported: {stats['success']}", "success")
                    self.log(f"❌ Failed: {stats['failed']}", "error")
                    
                    result = {
                        'total': len(pdf_files),
                        'successful': successful,
                        'failed': failed,
                        'export_stats': stats
                    }
                    
                except Exception as e:
                    self.log(f"❌ Export failed: {e}", "error")
                    result = None
            else:
                # No export requested or disabled
                if not self.export_to_sheets:
                    self.log("")
                    self.log("="*70, "bold")
                    self.log("💾 SAVING TO JSON (No Google Sheets Export)", "info")
                    self.log("="*70, "bold")
                else:
                    self.log("ℹ️  Google Sheets export disabled in config", "info")
                    
                result = {
                    'total': len(pdf_files),
                    'successful': successful,
                    'failed': failed
                }
                
            self.finish_processing(result)
            
        except Exception as e:
            self.log(f"❌ FATAL ERROR: {e}", "error")
            self.finish_processing(None)
            
    def finish_processing(self, result):
        """Finish processing and update UI"""
        self.processing = False
        
        # Stop progress bar
        self.progress_bar.stop()
        
        # Update buttons
        self.process_btn.config(state=tk.NORMAL)
        self.process_only_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
        # Update summary
        if result:
            total = result.get('total', 0)
            success = result.get('successful', 0)
            failed = result.get('failed', 0)
            
            if 'export_stats' in result:
                export_success = result['export_stats'].get('success', 0)
                summary = f"✅ Processed {total} PDFs | Exported {export_success} orders | {failed} errors"
                color = self.SUCCESS if failed == 0 else self.WARNING
            else:
                summary = f"✅ Processed {total} PDFs | {success} successful | {failed} failed"
                color = self.SUCCESS if failed == 0 else self.WARNING
                
            self.summary_label.config(text=summary, fg=color)
            
            # Show completion message
            if failed == 0:
                messagebox.showinfo(
                    "Success! 🎉",
                    f"All done!\n\n"
                    f"Processed: {total} PDFs\n"
                    f"Exported: {export_success if 'export_stats' in result else success} orders\n\n"
                    f"Click 'Open Google Sheets' to view results."
                )
            else:
                messagebox.showwarning(
                    "Completed with Errors",
                    f"Processing finished with some errors.\n\n"
                    f"Processed: {total} PDFs\n"
                    f"Successful: {success}\n"
                    f"Failed: {failed}\n\n"
                    f"Check the log for details."
                )
        else:
            self.summary_label.config(text="❌ Processing failed", fg=self.ERROR)
            messagebox.showerror(
                "Error",
                "Processing failed. Check the log for details."
            )
            
    def log(self, message, tag=""):
        """Add message to log text area"""
        self.log_text.config(state=tk.NORMAL)
        if tag:
            self.log_text.insert(tk.END, message + "\n", tag)
        else:
            self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.window.update_idletasks()
        
    def open_google_sheets(self):
        """Open Google Sheets in browser"""
        import webbrowser
        url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}"
        webbrowser.open(url)
        self.log("🔗 Opening Google Sheets in browser...", "info")
        
    def show_help(self):
        """Show help dialog"""
        help_text = """
🚚 Transport Document Processor - Quick Guide

📝 How to Use:
1. Click "Browse" and select folder with PDF files
2. Review the file count (make sure all PDFs are there)
3. Choose processing mode:
   • "Process & Export" - Extract data AND upload to Google Sheets
   • "Process Only" - Extract data, save to JSON (no upload)
4. Wait for processing to complete
5. Click "Open Google Sheets" to view results (if exported)

⚠️ Important:
• Make sure credentials.json is in utils/ folder (for export)
• PDFs must be transport order documents
• Processing may take a few minutes for many files
• You can click "Stop" to cancel at any time

💡 Tips:
• Use "Process Only" to test without uploading
• The app remembers your last folder
• Check the log for detailed information
• Green messages = success, Red = errors

❓ Need Help?
Contact your IT team or check the documentation.
        """
        
        help_window = tk.Toplevel(self.window)
        help_window.title("Help")
        help_window.geometry("500x400")
        help_window.resizable(False, False)
        
        text = scrolledtext.ScrolledText(
            help_window,
            font=("Arial", 10),
            wrap=tk.WORD,
            padx=20,
            pady=20
        )
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(1.0, help_text)
        text.config(state=tk.DISABLED)
        
        close_btn = tk.Button(
            help_window,
            text="Close",
            command=help_window.destroy,
            font=("Arial", 10),
            padx=20,
            pady=5
        )
        close_btn.pack(pady=10)
        
    def check_credentials(self):
        """Check if credentials file exists"""
        cred_path = Path(CREDENTIALS_FILE)
        if not cred_path.exists():
            self.log("⚠️  WARNING: credentials.json not found!", "warning")
            self.log(f"   Expected at: {cred_path.absolute()}", "warning")
            self.log("   Google Sheets export will not work!", "warning")
            self.log("")
            
            messagebox.showwarning(
                "Credentials Missing",
                f"Google Sheets credentials not found!\n\n"
                f"Expected location:\n{cred_path.absolute()}\n\n"
                f"Please add credentials.json to continue."
            )
        else:
            self.log("✅ Credentials found", "success")
            self.log("")
            
    def load_last_folder(self):
        """Load last used folder from config"""
        config_file = Path("gui_config.json")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('last_folder')
            except:
                pass
        return None
        
    def save_last_folder(self, folder):
        """Save last used folder to config"""
        config_file = Path("gui_config.json")
        config = {'last_folder': folder}
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f)
        except:
            pass
            
    def run(self):
        """Start the GUI application"""
        self.window.mainloop()


def main():
    """Main entry point"""
    app = TransportGUI()
    app.run()


if __name__ == "__main__":
    main()