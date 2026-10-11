"""Parcelas `n/N`: extração da descrição e a linha mínima usada para identidade e antecipação."""

import re
from dataclasses import dataclass

from app.domain.months import YearMonth

# Nubank: "Latam Air*0000 - Parcela 4/4".
_NUBANK_SUFFIX = re.compile(r"^(?P<root>.+?) - Parcela (?P<number>\d+)/(?P<total>\d+)$")
# Itaú: "MERCADOLIVRE*5525309/12" (colado) ou "SHOPEE *OLILOJA 03/05" (com espaço).
_ITAU_SUFFIX = re.compile(r"^(?P<root>.*?\S)\s?(?P<number>\d{2})/(?P<total>\d{2})$")


_NUBANK_TAIL = re.compile(r"^(?P<head>.+? - Parcela )\d+(?P<tail>/\d+)$")
_ITAU_TAIL = re.compile(r"^(?P<head>.*?\S\s?)\d{2}(?P<tail>/\d{2})$")


@dataclass(frozen=True)
class InstallmentInfo:
    root: str
    number: int
    total: int


@dataclass(frozen=True)
class InstallmentLine:
    """Uma parcela lida de um arquivo, com o que importa para ordinal, grupo e antecipação."""

    root: str
    total: int
    number: int
    first_month: YearMonth
    amount_cents: int
    competence: YearMonth


def parse_nubank_installment(title: str) -> InstallmentInfo | None:
    return _from_match(_NUBANK_SUFFIX.match(title.strip()))


def parse_itau_installment(description: str) -> InstallmentInfo | None:
    return _from_match(_ITAU_SUFFIX.match(description.strip()))


def _from_match(match: re.Match[str] | None) -> InstallmentInfo | None:
    if match is None:
        return None
    number, total = int(match["number"]), int(match["total"])
    if total < 2 or not 1 <= number <= total:
        return None
    return InstallmentInfo(root=match["root"].strip(), number=number, total=total)


def projected_description(description_raw: str, new_number: int) -> str:
    """Descrição de uma parcela projetada: a da última real com o `n` trocado por `new_number`.

    Nubank: ` - Parcela 3/4` → ` - Parcela 4/4`. Itaú: `MERCADOLIVRE*5525309/12` → `...5525310/12`
    (dois dígitos, colado ou com espaço). Sem sufixo reconhecível, devolve a descrição intacta.
    """
    text = description_raw.strip()
    if match := _NUBANK_TAIL.match(text):
        return f"{match['head']}{new_number}{match['tail']}"
    if match := _ITAU_TAIL.match(text):
        return f"{match['head']}{new_number:02d}{match['tail']}"
    return text
