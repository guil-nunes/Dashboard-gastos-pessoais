import pytest

from app.ingestion.registry import detect
from app.ingestion.types import RejectedFile


@pytest.mark.parametrize(
    ("relative", "adapter"),
    [
        ("nubank/Nubank_2026-08-08.csv", "nubank_cartao_csv"),
        ("nubank/NU_123456789_01SET2026_15SET2026.csv", "nubank_conta_csv"),
        ("nubank/NU_123456789_01SET2026_15SET2026.ofx", "ofx_conta"),
        ("itau/itau_extrato_A.pdf", "itau_conta_pdf"),
        ("itau/itau_fatura_2026-01.pdf", "itau_cartao_pdf"),
        ("itau/nubank_extrato.pdf", "nubank_pdf"),
    ],
)
def test_each_fixture_finds_its_adapter(fixture_file, relative, adapter):
    _, content = fixture_file(relative)
    assert detect(content).name == adapter


def test_nubank_pdf_points_to_supported_formats(fixture_file):
    name, content = fixture_file("itau/nubank_extrato.pdf")
    with pytest.raises(RejectedFile, match="importe o OFX da conta ou o CSV da fatura"):
        detect(content).parse(content, name)


def test_unknown_pdf_is_rejected(fixture_file):
    _, content = fixture_file("itau/desconhecido.pdf")
    with pytest.raises(RejectedFile, match="não reconhecido"):
        detect(content)


def test_corrupted_pdf_is_rejected():
    with pytest.raises(RejectedFile, match="PDF ilegível"):
        detect(b"%PDF-1.7\nisto nao e um pdf de verdade")


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"   \n",
        b"nome,valor\nmercado,10\n",
        b"\x00\x01\x02\xff",
    ],
)
def test_unknown_files_are_rejected(content):
    with pytest.raises(RejectedFile, match="não reconhecido"):
        detect(content)
