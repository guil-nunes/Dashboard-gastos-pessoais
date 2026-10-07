"""Desfazer uma importação (spec §7.4): atômico, uma transação SQL."""

from sqlalchemy.orm import Session

from app.repo import imports as repo


def undo_import(session: Session, batch_id: int) -> bool:
    """Remove o lote e as transações sem outra origem; False se o lote não existe."""
    batch = repo.get_batch(session, batch_id)
    if batch is None:
        return False
    account_id = batch.account_id
    try:
        repo.delete_batch(session, batch)
        repo.rebuild_projected(session, [account_id])
        session.commit()
    except Exception:
        session.rollback()
        raise
    return True
