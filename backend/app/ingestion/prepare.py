"""Estágios puros da importação (spec §7.2): detect → parse → normalize → classify → keys."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.classification.base import ClassificationInput
from app.classification.pipeline import classify
from app.domain.competence import apply_anticipation
from app.domain.installments import InstallmentLine
from app.domain.keys import (
    account_ref,
    dedup_key_external,
    dedup_key_row,
    identical_row_ordinals,
    installment_group_key,
    installment_ordinals,
)
from app.domain.months import YearMonth
from app.domain.normalizer import NORMALIZER_VERSION, normalize_merchant
from app.ingestion.registry import detect
from app.ingestion.types import AccountInfo, RawTransaction, RowError


@dataclass(frozen=True)
class PreparedTransaction:
    """Uma linha pronta para virar `transactions` (spec §8), sem os campos do banco."""

    occurred_on: date
    competence_month: str
    amount_cents: int
    description_raw: str
    external_id: str | None
    merchant_key: str
    normalizer_version: int
    kind: str
    ignore_reason: str | None
    suggested_ignore_reason: str | None
    bank_category: str | None
    category_id: int | None
    category_source: str
    category_confidence: float | None
    installment_number: int | None
    installment_total: int | None
    installment_group_key: str | None
    dedup_key: str


@dataclass(frozen=True)
class PreparedFile:
    filename: str
    file_sha256: str
    account: AccountInfo
    transactions: list[PreparedTransaction]
    errors: list[RowError]


def prepare(filename: str, content: bytes) -> PreparedFile:
    """Levanta `RejectedFile` se o arquivo não for reconhecido."""
    parsed = detect(content).parse(content, filename)
    account = parsed.account
    ref = account_ref(account.bank, account.kind, account.external_account_id)
    raws = parsed.transactions

    row_ordinals = identical_row_ordinals(
        [(raw.occurred_on, raw.amount_cents, raw.description_raw) for raw in raws]
    )
    groups, competences = _installment_groups(ref, raws)

    transactions = []
    for index, (raw, ordinal) in enumerate(zip(raws, row_ordinals, strict=True)):
        merchant_key = normalize_merchant(raw.description_raw)
        result = classify(
            ClassificationInput(
                account_kind=account.kind,
                amount_cents=raw.amount_cents,
                description_raw=raw.description_raw,
                merchant_key=merchant_key,
                bank_category=raw.bank_category,
            )
        )
        if raw.external_id:
            dedup_key = dedup_key_external(ref, raw.external_id)
        else:
            dedup_key = dedup_key_row(
                ref, raw.occurred_on, raw.amount_cents, raw.description_raw, ordinal
            )
        transactions.append(
            PreparedTransaction(
                occurred_on=raw.occurred_on,
                competence_month=str(competences.get(index, raw.competence)),
                amount_cents=raw.amount_cents,
                description_raw=raw.description_raw,
                external_id=raw.external_id,
                merchant_key=merchant_key,
                normalizer_version=NORMALIZER_VERSION,
                kind=result.kind,
                ignore_reason=result.ignore_reason,
                suggested_ignore_reason=result.suggested_ignore_reason,
                bank_category=raw.bank_category,
                category_id=result.category_id,
                category_source=result.source,
                category_confidence=result.confidence,
                installment_number=raw.installment.number if raw.installment else None,
                installment_total=raw.installment.total if raw.installment else None,
                installment_group_key=groups.get(index),
                dedup_key=dedup_key,
            )
        )

    return PreparedFile(
        filename=filename,
        file_sha256=hashlib.sha256(content).hexdigest(),
        account=account,
        transactions=transactions,
        errors=parsed.errors,
    )


def _installment_groups(
    ref: str, raws: Sequence[RawTransaction]
) -> tuple[dict[int, str], dict[int, YearMonth]]:
    """Chave de grupo (R10) e competência após a antecipação (Q14), por índice da linha."""
    indices = [i for i, raw in enumerate(raws) if raw.installment and raw.first_month]
    lines = [
        InstallmentLine(
            root=raws[i].installment.root,
            total=raws[i].installment.total,
            number=raws[i].installment.number,
            first_month=raws[i].first_month,
            amount_cents=raws[i].amount_cents,
            competence=raws[i].competence,
        )
        for i in indices
    ]
    ordinals = installment_ordinals(lines)
    groups = {
        i: installment_group_key(ref, line.root, line.total, line.first_month, ordinal)
        for i, line, ordinal in zip(indices, lines, ordinals, strict=True)
    }
    competences = dict(zip(indices, apply_anticipation(lines, ordinals), strict=True))
    return groups, competences
