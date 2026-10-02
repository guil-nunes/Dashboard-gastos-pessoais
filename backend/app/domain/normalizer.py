"""Normalizador versionado: `description_raw` → `merchant_key` (R5).

Mudou alguma regra? Incremente `NORMALIZER_VERSION` e rode `renormalize`.
"""

import re
import unicodedata

NORMALIZER_VERSION = 1

_IOF = re.compile(r'^IOF de "(?P<inner>.+)"$', re.IGNORECASE)
_NUBANK_INSTALLMENT = re.compile(r"\s+-\s+Parcela\s+\d+/\d+$", re.IGNORECASE)
# "DD/MM" colado no fim: parcela da fatura Itaú ou data da operação no extrato Itaú.
_TRAILING_DAY_MONTH = re.compile(r"\s?\d{2}/\d{2}$")
_DEBIT_PURCHASE = re.compile(r"^Compra no d[ée]bito\s+-\s+", re.IGNORECASE)
# Nubank conta: enviado e recebido geram a mesma chave; a estratégia 0 cuida da direção.
_NUBANK_PIX = re.compile(
    r"^Transfer[êe]ncia (?:enviada pelo Pix|recebida pelo Pix|Recebida)\s+-\s+"
    r"(?P<name>.+?)(?:\s+-\s+.*)?$",
    re.IGNORECASE,
)
_ITAU_PIX_TRANSFER = re.compile(r"^PIX TRANSF\s+", re.IGNORECASE)
_ITAU_PIX_AUTOMATIC = re.compile(r"^PIX AUT\s+", re.IGNORECASE)
_ITAU_DEBIT_PURCHASE = re.compile(r"^(?:ON|PAY)\s+", re.IGNORECASE)
# Adquirentes/gateways; marketplaces (SHOPEE, MERCADOLIVRE) ficam, pois identificam a loja.
_GATEWAY_PREFIX = re.compile(r"^(?:IFD|DM|MP|PAG|APP|PG|ZP)\s*\*\s*", re.IGNORECASE)
_NON_ALPHANUMERIC = re.compile(r"[^A-Z0-9 ]+")


def normalize_merchant(description_raw: str) -> str:
    text = description_raw.strip()

    if match := _IOF.match(text):
        text = match["inner"].strip()
    text = _NUBANK_INSTALLMENT.sub("", text)
    text = _TRAILING_DAY_MONTH.sub("", text).strip()

    if match := _NUBANK_PIX.match(text):
        text = "PIX " + match["name"]
    elif _ITAU_PIX_TRANSFER.match(text):
        text = _ITAU_PIX_TRANSFER.sub("PIX ", text)
    else:
        text = _DEBIT_PURCHASE.sub("", text)
        text = _ITAU_PIX_AUTOMATIC.sub("", text)
        text = _ITAU_DEBIT_PURCHASE.sub("", text)
        text = _GATEWAY_PREFIX.sub("", text)

    return _clean(text)


def _clean(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    tokens = _NON_ALPHANUMERIC.sub(" ", ascii_text.upper()).split()
    words = [token for token in tokens if not token.isdigit()] or tokens
    deduplicated = [word for i, word in enumerate(words) if i == 0 or word != words[i - 1]]
    return " ".join(deduplicated)
