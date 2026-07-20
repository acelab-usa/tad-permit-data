import fitz

def extract_text_from_pdf(pdf_path, page_limit=5):
    """
    Opens a local PDF file and extracts all raw text layouts.
    """
    try:
        text_content = []
        # Open the PDF document
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                if i >= page_limit:
                    break
                # Extract text using standard layout grouping
                text_content.append(page.get_text())
                
        # Join all pages with a clear separator
        full_text = "\n--- PAGE BREAK ---\n".join(text_content)
        return full_text.strip()
        
    except Exception as e:
        print(f"❌ PyMuPDF failed to read file at {pdf_path}: {e}")
        return None