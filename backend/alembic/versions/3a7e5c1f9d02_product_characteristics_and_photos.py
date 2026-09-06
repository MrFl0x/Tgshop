"""product characteristics and photo gallery

Revision ID: 3a7e5c1f9d02
Revises: 9c1f2a4e7b3d
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a7e5c1f9d02'
down_revision: Union[str, Sequence[str], None] = '9c1f2a4e7b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('products', sa.Column('characteristics', sa.JSON(), nullable=True))
    op.execute("UPDATE products SET characteristics = '{}' WHERE characteristics IS NULL")
    op.alter_column('products', 'characteristics', existing_type=sa.JSON(), nullable=False)

    op.create_table(
        'product_photos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('image_upload', sa.String(length=500), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('product_photos')
    op.drop_column('products', 'characteristics')
