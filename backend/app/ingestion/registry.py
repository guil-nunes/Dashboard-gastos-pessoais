"""Detecção do formato pelo conteúdo: cada adapter reconhece o seu; nenhum casou → rejeita.

Texto (CSV, OFX): `sniff(head)` com os primeiros bytes. PDF: o texto da 1ª página é extraído
uma vez e passado a `sniff_text`, porque todo PDF começa igual (`%PDF`).
"""

from app.ingestion.adapters.base import Adapter, PdfAdapter
from app.ingestion.adapters.itau_account_pdf import ItauAccountPdf
from app.ingestion.adapters.itau_card_pdf import ItauCardPdf
from app.ingestion.adapters.nubank_account_csv import NubankAccountCsv
from app.ingestion.adapters.nubank_card_csv import NubankCardCsv
from app.ingestion.adapters.nubank_pdf import NubankPdf
from app.ingestion.adapters.ofx import OfxAdapter
from app.ingestion.pdf import first_page_text
from app.ingestion.types import RejectedFile

ADAPTERS: list[Adapter] = [NubankCardCsv(), NubankAccountCsv(), OfxAdapter()]
PDF_ADAPTERS: list[PdfAdapter] = [ItauAccountPdf(), ItauCardPdf(), NubankPdf()]
HEAD_SIZE = 4096
UNKNOWN = "formato de arquivo não reconhecido"


def detect(content: bytes) -> Adapter | PdfAdapter:
    if content.lstrip()[:5] == b"%PDF-":
        first_page = first_page_text(content)
        for pdf_adapter in PDF_ADAPTERS:
            if pdf_adapter.sniff_text(first_page):
                return pdf_adapter
        raise RejectedFile(UNKNOWN)

    head = content[:HEAD_SIZE]
    for adapter in ADAPTERS:
        if adapter.sniff(head):
            return adapter
    raise RejectedFile(UNKNOWN)
