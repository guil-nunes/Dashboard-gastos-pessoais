"""Leitura de PDF por posição das palavras (pdfplumber), para os adapters do Itaú."""

import io
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import pdfplumber
from pdfplumber.page import Page

from app.ingestion.types import RejectedFile

# Palavras cujo topo difere menos que isso estão na mesma linha.
LINE_TOLERANCE = 3.0


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    x1: float
    top: float


@contextmanager
def open_pdf(content: bytes) -> Iterator[pdfplumber.PDF]:
    try:
        pdf = pdfplumber.open(io.BytesIO(content))
        pdf.pages  # noqa: B018 - força a leitura da estrutura para validar o arquivo
    except Exception as error:  # pdfminer levanta vários tipos para PDF inválido ou com senha
        raise RejectedFile(f"PDF ilegível: {error.__class__.__name__}") from error
    try:
        yield pdf
    finally:
        pdf.close()


def first_page_text(content: bytes) -> str:
    with open_pdf(content) as pdf:
        return (pdf.pages[0].extract_text() or "") if pdf.pages else ""


def page_lines(page: Page, x0: float | None = None, x1: float | None = None) -> list[list[Word]]:
    """Linhas (de cima para baixo) de palavras ordenadas por x, opcionalmente só entre x0 e x1."""
    region = page if x0 is None else page.crop((x0, 0, x1, page.height))
    words = [
        Word(w["text"], w["x0"], w["x1"], w["top"])
        for w in region.extract_words(keep_blank_chars=False, use_text_flow=False)
    ]
    lines: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (w.top, w.x0)):
        if lines and abs(lines[-1][0].top - word.top) <= LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda w: w.x0) for line in lines]


def line_text(line: list[Word]) -> str:
    return " ".join(word.text for word in line)
