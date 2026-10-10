"""Estratégia 2: regras de palavra-chave (spec R6).

Casam na descrição original e no `merchant_key`: o normalizador remove prefixos como `Ifd*`.
"""

import re

from app.classification.base import Classification, ClassificationInput, KeywordRuleEntry

RULE_CONFIDENCE = 0.9


class KeywordStrategy:
    def __init__(self, rules: tuple[KeywordRuleEntry, ...]) -> None:
        self._rules = rules

    def classify(self, item: ClassificationInput) -> Classification | None:
        haystacks = (item.description_raw.casefold(), item.merchant_key.casefold())
        for rule in self._rules:
            if not _matches(rule, haystacks):
                continue
            if rule.kind == "ignorar":
                continue  # regra não carrega motivo de ignorar (só estrutural ou usuário)
            return Classification(
                kind="despesa",
                category_id=rule.category_id,
                source="regra",
                confidence=RULE_CONFIDENCE,
            )
        return None


def _matches(rule: KeywordRuleEntry, haystacks: tuple[str, ...]) -> bool:
    if rule.match_type == "regex":
        try:
            return any(re.search(rule.pattern, text, re.IGNORECASE) for text in haystacks)
        except re.error:
            return False
    needle = rule.pattern.casefold()
    return any(needle in text for text in haystacks)
