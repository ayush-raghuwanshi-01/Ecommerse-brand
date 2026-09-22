"""add_product_mrp_paise

Revision ID: 03bcccdf3439
Revises: f7f0f950a5c9
Create Date: 2026-09-22

Adds the optional displayed-MRP column (Legal Metrology) so the storefront can
render a strikethrough price and % off, the standard conversion pattern on
Indian D2C storefronts. Nullable: legacy rows simply show no MRP.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "03bcccdf3439"
down_revision = "f7f0f950a5c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("mrp_paise", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "mrp_paise")
