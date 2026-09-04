"""
Слой оплаты. Сейчас единственная реализация — StubPaymentProvider: она сразу
подтверждает оплату без реального списания денег. Когда будет оформлено
юрлицо и договор с ЮKassa, добавляется YooKassaProvider с тем же интерфейсом
(charge) — роутер orders.py и админку менять не придётся.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PaymentResult:
    success: bool
    provider_payment_id: str
    note: str = ""


class PaymentProvider(ABC):
    @abstractmethod
    def charge(self, order_id: int, amount: float) -> PaymentResult:
        ...


class StubPaymentProvider(PaymentProvider):
    """Заглушка вместо ЮKassa. Всегда возвращает успех — использовать только
    до подключения реального провайдера."""

    def charge(self, order_id: int, amount: float) -> PaymentResult:
        return PaymentResult(
            success=True,
            provider_payment_id=f"stub-{order_id}",
            note="Оплата не проводилась — заглушка PaymentStub, деньги не списаны",
        )


def get_payment_provider() -> PaymentProvider:
    # TODO(payments): когда будет договор с ЮKassa — переключить на YooKassaProvider,
    # например через переменную окружения PAYMENT_PROVIDER=yookassa.
    return StubPaymentProvider()
