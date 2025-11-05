# extractors/pdf_reader.py
"""PDF text extraction module"""

import PyPDF2
import os


class PDFReader:
    """Handle PDF file reading and text extraction"""
    
    def __init__(self, pdfs_folder):
        self.pdfs_folder = pdfs_folder
    
    def list_pdf_files(self):
        """Get list of all PDF files in folder"""
        if not os.path.exists(self.pdfs_folder):
            print(f"❌ Folder '{self.pdfs_folder}' does not exist!")
            return []
        
        pdf_files = [
            f for f in os.listdir(self.pdfs_folder) 
            if f.lower().endswith('.pdf')
        ]
        
        return sorted(pdf_files)
    
    def extract_text(self, pdf_path):
        """Extract text from a PDF file"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                
                return text
        
        except Exception as e:
            raise Exception(f"Error reading PDF: {e}")
    
    def get_file_size(self, pdf_path):
        """Get file size in KB"""
        try:
            size_bytes = os.path.getsize(pdf_path)
            return size_bytes / 1024
        except:
            return 0