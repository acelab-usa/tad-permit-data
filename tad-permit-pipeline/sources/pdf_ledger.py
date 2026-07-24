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

    def iter_pages(self, month_cap: int = 1, page_cap=None, start_filename: str | None = None, start_page: int = 0):
        """Yields (filename, page_number, page_text), resuming from
        `start_filename`/`start_page` (see database.get_pdf_cursor()) instead
        of always restarting at the first file's page 1.

        Without this, a repeated run (scheduled or manual) would re-read --
        and the caller would re-queue a Hatchet event for -- the exact same
        pages every time, since there was previously no memory of prior
        progress at all.

        `start_filename` is only special for the *first* file resumed into;
        every subsequent file starts fresh from page 1. If a file turns out
        to already be fully consumed (the resume point is past its last
        page), it contributes nothing and doesn't count against `month_cap`
        -- otherwise an exhausted file at the front of the list would get
        stuck here forever, never advancing to the next one.
        """
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

        start_index = pdf_files.index(start_filename) if start_filename in pdf_files else 0
        remaining_budget = page_cap  # None means unlimited
        files_advanced = 0

        for filename in pdf_files[start_index:]:
            if files_advanced >= month_cap:
                break

            resume_page = start_page if filename == start_filename else 0
            local_path = os.path.join(self.folder_path, filename)
            logger.info(
                "%s: opening monthly compilation report '%s' (resuming after page %s)",
                self.name, filename, resume_page,
            )

            yielded_any = False
            try:
                for page_number, page_text in iter_pdf_pages(
                    local_path, page_cap=remaining_budget, start_page=resume_page
                ):
                    yielded_any = True
                    yield filename, page_number, page_text
                    if remaining_budget is not None:
                        remaining_budget -= 1
            except Exception as e:
                logger.error("%s: failed to open/split '%s', skipping file: %s", self.name, filename, e)
                continue

            if yielded_any:
                files_advanced += 1

            if remaining_budget is not None and remaining_budget <= 0:
                break
