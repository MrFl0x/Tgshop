"""rebuild orders section Ozon-style (new statuses, promo codes, returns)

По прямому запросу — старые заказы удаляются целиком (не переносятся на
новые статусы), см. tz-zakazy.md, п.4-5 и обсуждение в чате. Схема Order
после этой миграции: новые статусы (awaiting_payment → awaiting_packaging →
awaiting_deliver → delivering → delivered/cancelled/returned), промокоды
(discount_total/promo_code), человекочитаемый number, pickup_point,
customer_comment/admin_comment, payment_method. Плюс новые таблицы: returns
(возврат целого заказа) и promo_codes (коды скидок).

Revision ID: 3f0a1c7e2b6d
Revises: 3a7e5c1f9d02
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f0a1c7e2b6d'
down_revision: Union[str, Sequence[str], None] = '3a7e5c1f9d02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 0. stock_movements не чистим (это независимый журнал, старые записи
    # остаются) — просто добавляем новое значение причины списания для
    # возврата, оформленного через карточку заказа (см. app/admin_orders.py).
    # ADD VALUE — аддитивно, безопасно на непустой таблице/типе.
    op.execute("ALTER TYPE stockmovementreason ADD VALUE IF NOT EXISTS 'RETURNED'")

    # 1. Снести старые заказы и всё, что на них ссылается (FK-safe порядок).
    # Склад/бонусы — это самостоятельные журналы, а не "заказы": не удаляем
    # их целиком, просто отвязываем от несуществующих больше заказов.
    op.execute("DELETE FROM order_status_history")
    op.execute("DELETE FROM payment_transactions WHERE order_id IS NOT NULL")
    op.execute("UPDATE bonus_transactions SET related_order_id = NULL WHERE related_order_id IS NOT NULL")
    op.execute("UPDATE stock_movements SET order_id = NULL WHERE order_id IS NOT NULL")
    op.execute("DELETE FROM order_items")
    op.execute("DELETE FROM orders")

    # 2. Пересоздать статусные enum'ы — таблицы уже пусты, поэтому проще
    # выкинуть колонки и старый тип и завести новые, чем городить USING-каст.
    # orderstatus используется НЕ только в orders.status, но и в
    # order_status_history.from_status/to_status — все три колонки нужно
    # снести до DROP TYPE, иначе Postgres откажет (DependentObjectsStillExist).
    op.drop_column('orders', 'status')
    op.drop_column('order_status_history', 'from_status')
    op.drop_column('order_status_history', 'to_status')
    op.execute("DROP TYPE IF EXISTS orderstatus")
    _order_status_labels = [
        'AWAITING_PAYMENT', 'AWAITING_PACKAGING', 'AWAITING_DELIVER',
        'DELIVERING', 'DELIVERED', 'CANCELLED', 'RETURNED',
    ]
    sa.Enum(*_order_status_labels, name='orderstatus').create(op.get_bind(), checkfirst=True)
    op.add_column(
        'orders',
        sa.Column('status', sa.Enum(*_order_status_labels, name='orderstatus', create_type=False), nullable=False),
    )
    op.add_column(
        'order_status_history',
        sa.Column('from_status', sa.Enum(*_order_status_labels, name='orderstatus', create_type=False), nullable=True),
    )
    op.add_column(
        'order_status_history',
        sa.Column('to_status', sa.Enum(*_order_status_labels, name='orderstatus', create_type=False), nullable=False),
    )

    op.drop_column('orders', 'payment_status')
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    payment_status_enum = sa.Enum('PENDING', 'PAID', 'FAILED', 'REFUNDED', name='paymentstatus')
    payment_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('orders', sa.Column('payment_status', payment_status_enum, nullable=False))

    # 3. Новые поля заказа.
    # Отдельная последовательность для номера заказа — НЕ orders_id_seq: номер
    # нужен ДО первого INSERT (number — NOT NULL), а order.id известен только
    # ПОСЛЕ него. Конкурентно-безопасно (nextval атомарен), в отличие от
    # варианта "снять id после flush и потом UPDATE".
    op.execute("CREATE SEQUENCE IF NOT EXISTS order_number_seq")
    op.add_column('orders', sa.Column('number', sa.String(length=32), nullable=False))
    op.create_index('ix_orders_number', 'orders', ['number'], unique=True)
    op.add_column('orders', sa.Column('pickup_point', sa.Text(), nullable=False, server_default=''))
    op.add_column('orders', sa.Column('discount_total', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('promo_code', sa.String(length=32), nullable=True))
    op.add_column('orders', sa.Column('payment_method', sa.String(length=20), nullable=False, server_default='card'))
    op.add_column('orders', sa.Column('customer_comment', sa.Text(), nullable=False, server_default=''))
    op.add_column('orders', sa.Column('admin_comment', sa.Text(), nullable=False, server_default=''))
    # server_default только чтобы ALTER прошёл на (пустой) таблице задним
    # числом не нужен — но раз уж он тут есть, снимаем, чтобы не расходиться
    # с остальными колонками проекта (default всегда на стороне Python/ORM).
    op.alter_column('orders', 'pickup_point', server_default=None)
    op.alter_column('orders', 'discount_total', server_default=None)
    op.alter_column('orders', 'payment_method', server_default=None)
    op.alter_column('orders', 'customer_comment', server_default=None)
    op.alter_column('orders', 'admin_comment', server_default=None)

    # 4. Снимок суммы строки заказа.
    op.add_column('order_items', sa.Column('subtotal', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.alter_column('order_items', 'subtotal', server_default=None)

    # 5. Возвраты — целиком по заказу (см. модуль models.py:Return).
    return_status_enum = sa.Enum('REQUESTED', 'APPROVED', 'REJECTED', 'COMPLETED', name='returnstatus')
    op.create_table(
        'returns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', return_status_enum, nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    # 6. Промокоды.
    discount_type_enum = sa.Enum('PERCENT', 'FIXED', name='discounttype')
    op.create_table(
        'promo_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('discount_type', discount_type_enum, nullable=False),
        sa.Column('discount_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_promo_codes_code', 'promo_codes', ['code'], unique=True)


def downgrade() -> None:
    """Downgrade schema. Данные удалённых при upgrade() заказов не
    восстанавливаются — откат возвращает только форму схемы."""
    op.drop_index('ix_promo_codes_code', table_name='promo_codes')
    op.drop_table('promo_codes')
    op.execute("DROP TYPE IF EXISTS discounttype")

    op.drop_table('returns')
    op.execute("DROP TYPE IF EXISTS returnstatus")

    op.drop_column('order_items', 'subtotal')

    op.drop_column('orders', 'admin_comment')
    op.drop_column('orders', 'customer_comment')
    op.drop_column('orders', 'payment_method')
    op.drop_column('orders', 'promo_code')
    op.drop_column('orders', 'discount_total')
    op.drop_column('orders', 'pickup_point')
    op.drop_index('ix_orders_number', table_name='orders')
    op.drop_column('orders', 'number')
    op.execute("DROP SEQUENCE IF EXISTS order_number_seq")

    op.drop_column('orders', 'payment_status')
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    old_payment_status_enum = sa.Enum('PENDING', 'PAID', 'FAILED', name='paymentstatus')
    old_payment_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('orders', sa.Column('payment_status', old_payment_status_enum, nullable=False))

    op.drop_column('orders', 'status')
    op.drop_column('order_status_history', 'from_status')
    op.drop_column('order_status_history', 'to_status')
    op.execute("DROP TYPE IF EXISTS orderstatus")
    _old_order_status_labels = ['NEW', 'PAID', 'ASSEMBLED', 'SHIPPED', 'DELIVERED', 'CANCELLED']
    sa.Enum(*_old_order_status_labels, name='orderstatus').create(op.get_bind(), checkfirst=True)
    op.add_column(
        'orders',
        sa.Column('status', sa.Enum(*_old_order_status_labels, name='orderstatus', create_type=False), nullable=False),
    )
    op.add_column(
        'order_status_history',
        sa.Column('from_status', sa.Enum(*_old_order_status_labels, name='orderstatus', create_type=False), nullable=True),
    )
    op.add_column(
        'order_status_history',
        sa.Column('to_status', sa.Enum(*_old_order_status_labels, name='orderstatus', create_type=False), nullable=False),
    )
