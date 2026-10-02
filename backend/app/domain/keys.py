"""Chaves de identidade (R2, R10): só dados brutos do arquivo, nunca o `merchant_key`."""

import hashlib
from collections import defaultdict
from collections.abc import Hashable, Sequence
from datetime import date

from app.domain.installments import InstallmentLine
from app.domain.months import YearMonth


def account_ref(bank: str, kind: str, external_account_id: str = "") -> str:
    """Identidade estável da conta, calculável antes de existir linha no banco de dados."""
    return f"{bank}:{kind}:{external_account_id}"


def identical_row_ordinals(rows: Sequence[Hashable]) -> list[int]:
    """Posição (1, 2, 3…) de cada linha entre as linhas idênticas do mesmo arquivo.

    Linhas idênticas são indistinguíveis, então o resultado não depende da ordem do arquivo.
    """
    seen: dict[Hashable, int] = defaultdict(int)
    ordinals = []
    for row in rows:
        seen[row] += 1
        ordinals.append(seen[row])
    return ordinals


def dedup_key_external(account: str, external_id: str) -> str:
    return f"ext:{account}:{external_id}"


def dedup_key_row(
    account: str, occurred_on: date, amount_cents: int, description_raw: str, ordinal: int
) -> str:
    return "row:" + _digest(
        account, occurred_on.isoformat(), amount_cents, description_raw, ordinal
    )


def installment_ordinals(lines: Sequence[InstallmentLine]) -> list[int]:
    """Ordinal entre parcelas do mesmo arquivo com mesmo root, N, n e mês da 1ª parcela.

    Ordenadas por valor, distingue compras parceladas idênticas feitas no mesmo mês.
    """
    groups: dict[tuple, list[int]] = defaultdict(list)
    for index, line in enumerate(lines):
        groups[(line.root, line.total, line.number, line.first_month)].append(index)

    ordinals = [0] * len(lines)
    for indices in groups.values():
        ranked = sorted(indices, key=lambda i: lines[i].amount_cents)
        for position, index in enumerate(ranked, start=1):
            ordinals[index] = position
    return ordinals


def installment_group_key(
    account: str, root: str, total: int, first_month: YearMonth, ordinal: int
) -> str:
    """Sem valor da parcela (centavos de arredondamento) e sem `merchant_key` (muda com versão)."""
    return "grp:" + _digest(account, root, total, first_month, ordinal)


def _digest(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()
