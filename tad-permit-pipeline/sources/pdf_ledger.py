"""Generic adapter for jurisdictions that publish monthly PDF permit ledgers.

Adding a new PDF-ledger city is just:

    PDFLedgerSource(name="somecity", folder_path="./somecity_pdfs")

No per-city mapping function is needed -- the LLM extractor
(`llm_processor.extract_multiple_permits_from_text`) reads each page and
finds every permit listed on it, since ledger layouts vary too much
page-to-page to hand-write a parser per city.

If a city's ledger has quirks the generic extraction prompt won't know
about on its own (a specific permit-number pattern, category names,
formatting to ignore), pass `extraction_hints` -- see the `allen` entry in
`sources/registry.py` for an example. Leave it unset for a new city until
you've actually seen its output and know it needs tuning; a guessed hint
for an unfamiliar format is as likely to hurt as help.
"""
import os

from logging_setup import get_logger
from pdf_processor import iter_pdf_pages
from sources.base import PDFPermitSource

logger = get_logger("sources.pdf_ledger")


class PDFLedgerSource(PDFPermitSource):
    def __init__(self, name: str, folder_path: str, extraction_hints: str | None = None):
        self.name = name
        self.folder_path = folder_path
        self.extraction_hints = extraction_hints

    def iter_pages(self, month_cap: int = 1, page_cap=None):
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
            logger.warning(
                "%s: folder '%s' did not exist -- created it. Drop PDF files "
                "there and re-run.", self.name, self.folder_path,
            )
            return

        pdf_files = sorted(
            f for f in os.listdir(self.folder_path) if f.lower().endswith(".pdf")
        )
        if not pdf_files:
            logger.warning("%s: no PDF files found in '%s'", self.name, self.folder_path)
            return

        for filename in pdf_files[:month_cap]:
            local_path = os.path.join(self.folder_path, filename)
            logger.info("%s: opening monthly compilation report '%s'", self.name, filename)

            try:
                for page_number, page_text in iter_pdf_pages(local_path, page_cap=page_cap):
                    yield filename, page_number, page_text
            except Exception as e:
                logger.error("%s: failed to open/split '%s', skipping file: %s", self.name, filename, e)
                continue
