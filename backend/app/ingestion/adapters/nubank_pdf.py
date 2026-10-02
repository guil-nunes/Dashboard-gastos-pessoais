"""PDF do Nubank: não suportado (spec Anexo A.4), mas reconhecido para orientar o usuário."""

from app.ingestion.types import ParsedFile, RejectedFile


class NubankPdf:
    name = "nubank_pdf"

    def sniff_text(self, first_page: str) -> bool:
        text = first_page.casefold()
        return "nu pagamentos" in text or "nubank" in text

    def parse(self, content: bytes, filename: str) -> ParsedFile:
        raise RejectedFile(
            "PDF do Nubank não é suportado: importe o OFX da conta ou o CSV da fatura"
        )
