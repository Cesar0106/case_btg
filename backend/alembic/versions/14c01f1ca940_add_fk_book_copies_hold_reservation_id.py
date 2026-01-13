"""
Add FK constraint: book_copies.hold_reservation_id -> reservations.id

This migration adds referential integrity between book_copies and reservations.
When a copy is ON_HOLD, hold_reservation_id points to the reservation that holds it.
ON DELETE SET NULL ensures that if a reservation is deleted, the copy becomes available.

Revision ID: 14c01f1ca940
Revises: bc96d9edf06f
Create Date: 2026-01-12 22:16:06.727989
"""

from typing import Sequence, Union

from alembic import op


revision: str = "14c01f1ca940"
down_revision: Union[str, Sequence[str], None] = "bc96d9edf06f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = "fk_book_copies_hold_reservation_id"


def upgrade() -> None:
    """
    Add foreign key constraint from book_copies.hold_reservation_id to reservations.id.

    Rule: ON DELETE SET NULL
    - When a reservation is deleted, the copy's hold_reservation_id becomes NULL
    - This allows the copy to return to AVAILABLE status
    """
    op.create_foreign_key(
        constraint_name=CONSTRAINT_NAME,
        source_table="book_copies",
        referent_table="reservations",
        local_cols=["hold_reservation_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove the foreign key constraint."""
    op.drop_constraint(
        constraint_name=CONSTRAINT_NAME,
        table_name="book_copies",
        type_="foreignkey",
    )
