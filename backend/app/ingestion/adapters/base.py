from typing import Protocol

from app.ingestion.types import ParsedFile


class Adapter(Protocol):
    """Um formato de arquivo de um banco. Novo banco = novo adapter registrado em `registry.py`."""

    name: str

    def sniff(self, head: bytes) -> bool:
        """Reconhece o formato pelos primeiros bytes do arquivo."""
        ...

    def parse(self, content: bytes, filename: str) -> ParsedFile: ...


class PdfAdapter(Protocol):
    """Formato em PDF: todo PDF começa com `%PDF`, então reconhece pelo texto da 1ª página."""

    name: str

    def sniff_text(self, first_page: str) -> bool: ...

    def parse(self, content: bytes, filename: str) -> ParsedFile: ...
