import fitz

from logging_setup import get_logger

logger = get_logger("pdf_processor")


def extract_text_from_pdf(pdf_path, page_limit=5):
    """
    Opens a local PDF file and extracts all raw text layouts.
    """
    try:
        text_content = []
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                if i >= page_limit:
                    break
                text_content.append(page.get_text())

        full_text = "\n--- PAGE BREAK ---\n".join(text_content)
        return full_text.strip()

    except Exception as e:
        logger.error("PyMuPDF failed to read file at %s: %s", pdf_path, e)
        return None


def iter_pdf_pages(pdf_path, page_cap=None):
    """
    Opens a local PDF file and yields (page_number, page_text) for each
    non-blank page, using layout-preserving extraction (sorted reading order)
    suited to tabular ledger reports.

    A single corrupt/unreadable page is logged and skipped rather than
    aborting the whole document; a corrupt document raises so the caller can
    decide whether to skip the whole file.
    """
    with fitz.open(pdf_path) as doc:
        total_pages = page_cap if page_cap is not None else len(doc)
        total_pages = min(total_pages, len(doc))

        for page_idx in range(total_pages):
            try:
                page = doc[page_idx]
                page_text = page.get_text("text", sort=True)
            except Exception as e:
                logger.warning("Failed to extract page %s from %s: %s", page_idx + 1, pdf_path, e)
                continue

            if not page_text or not page_text.strip():
                continue

            yield page_idx + 1, page_text
