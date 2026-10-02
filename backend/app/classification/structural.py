"""Estratégia 0: regras estruturais por sinal e tipo de conta (spec R4).

Roda antes da memória: um Pix recebido continua `ignorar/receita` mesmo que o mesmo
`merchant_key` tenha memória de despesa. Saída para o próprio titular não é regra
estrutural (Q15): segue como despesa.
"""

from app.classification.base import Classification, ClassificationInput


def _ignore(reason: str) -> Classification:
    return Classification(kind="ignorar", ignore_reason=reason, source="regra", confidence=1.0)


class StructuralRules:
    def classify(self, item: ClassificationInput) -> Classification | None:
        description = item.description_raw.strip().casefold()
        if item.account_kind == "conta":
            if item.amount_cents < 0:  # todo crédito na conta
                return _ignore("receita")
            if description.startswith("pagamento de fatura"):
                return _ignore("pagamento_fatura")
        if item.account_kind == "cartao" and description == "pagamento recebido":
            return _ignore("pagamento_fatura")
        return None
