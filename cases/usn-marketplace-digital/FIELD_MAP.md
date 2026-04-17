# Маппинг полей API → события (заполнить)

Скопируй сюда **имена полей** из реальных ответов API (без токенов и персональных данных).

## Маркетплейс

| Наш payload | Поле API | Примечание |
|-------------|-----------|------------|
| `order_id` | | |
| `gross_amount` | | |
| `payout_id` | | |
| `commission` | | |
| `net_to_seller` | | |

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
