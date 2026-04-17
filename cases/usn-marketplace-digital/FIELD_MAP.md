# Маппинг полей API → события (заполнить)

Скопируй сюда **имена полей** из реальных ответов API (без токенов и персональных данных).

## Маркетплейс (Яндекс)

Сводка методов и отчётов: [docs/integrations/yandex-market-api-for-ledger.md](../../docs/integrations/yandex-market-api-for-ledger.md).

| Наш payload | Поле API | Примечание |
|-------------|-----------|------------|
| `order_id` | `orderId` (POST `v1/businesses/.../orders`) | Плюс уведомления `ORDER_*` |
| `gross_amount` | из позиций заказа / отчёта по заказам | Уточнить по выбранному отчёту |
| `payout_id` / batch | из отчёта по платежам `united-netting` | См. `TRANSACTION_ID`, период, `BANK_ORDER_*` |
| `commission` | услуги Маркета в отчётах | Листы услуг / маржа |
| `net_to_seller` | суммы к выплате в отчёте по платежам | Сверка с `BANK_IN` |

## Банк

| Наш payload | Поле выписки / API | Примечание |
|-------------|---------------------|------------|
| `bank_tx_id` | *(из JSON выписки — уточнить по OpenAPI)* | Должен совпадать с **`paymentId`** из JWT вебхука `incomingPayment` / `outgoingPayment`, если дока банка это гарантирует |
| `amount` | `amount` / `amountNat` | `amount` — в валюте счёта; `amountNat` — в RUB по курсу ЦБ |
| `purpose` | назначение платежа в теле операции | Для мэтча с выплатой маркетплейса |
| `direction` | `creditDebitIndicator` | `credit` → `BANK_IN`, `debit` → `BANK_OUT` |

**Точка (Tochka):** выжимка и ссылки на методы — [docs/integrations/tochka-api-for-ledger.md](../../docs/integrations/tochka-api-for-ledger.md). Точные имена полей строки выписки — из ответа **Get Statement** в актуальной версии OpenAPI.

## Поставщик

| Наш payload | Поле API | Примечание |
|-------------|-----------|------------|
| `delivery_id` | | |
| `product_id` | | |
| `unit_price` | | |
