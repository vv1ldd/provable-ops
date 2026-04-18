# Маппинг полей API → события (заполнить)

Скопируй сюда **имена полей** из реальных ответов API (без токенов и персональных данных).

## Маркетплейс (Яндекс)

Сводка методов и отчётов: [docs/integrations/yandex-market-api-for-ledger.md](../../docs/integrations/yandex-market-api-for-ledger.md).


| Наш payload         | Поле API                                    | Примечание                                   |
| ------------------- | ------------------------------------------- | -------------------------------------------- |
| `order_id`          | `orderId` (POST `v1/businesses/.../orders`) | Плюс уведомления `ORDER_*`                   |
| `gross_amount`      | из позиций заказа / отчёта по заказам       | Уточнить по выбранному отчёту                |
| `payout_id` / batch | из отчёта по платежам `united-netting`      | См. `TRANSACTION_ID`, период, `BANK_ORDER_*` |
| `commission`        | услуги Маркета в отчётах                    | Листы услуг / маржа                          |
| `net_to_seller`     | суммы к выплате в отчёте по платежам        | Сверка с `BANK_IN`                           |
| `sku_marketplace`   | `shopSku` / offer / позиция заказа          | **Ваш** SKU в потоке Маркета (как завели оффер); при единой политике именования **совпадает** с ключом в прокси |


## Банк


| Наш payload  | Поле выписки / API                        | Примечание                                                                                                               |
| ------------ | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `bank_tx_id` | *(из JSON выписки — уточнить по OpenAPI)* | Должен совпадать с **paymentId** из JWT вебхука `incomingPayment` / `outgoingPayment`, если дока банка это гарантирует |
| `amount`     | `amount` / `amountNat`                    | `amount` — в валюте счёта; `amountNat` — в RUB по курсу ЦБ                                                               |
| `purpose`    | назначение платежа в теле операции        | Для мэтча с выплатой маркетплейса                                                                                        |
| `direction`  | `creditDebitIndicator`                    | `credit` → `BANK_IN`, `debit` → `BANK_OUT`                                                                               |


**Точка (Tochka):** выжимка и ссылки на методы — [docs/integrations/tochka-api-for-ledger.md](../../docs/integrations/tochka-api-for-ledger.md). Точные имена полей строки выписки — из ответа **Get Statement** в актуальной версии OpenAPI.

## Поставщик (EZ PIN / EZPayPin)

Сводка: [docs/integrations/ezpaypin-api-for-ledger.md](../../docs/integrations/ezpaypin-api-for-ledger.md). Полная OpenAPI-выжимка может храниться отдельным файлом `ezpaypin-openapi-v2.0.2-reference.md` у вас в монорепо.

| Наш payload        | Поле API (POST `/orders/`) | Примечание                                      |
| ------------------ | -------------------------- | ----------------------------------------------- |
| `supplier_tx`      | ответ Order (id, время)  | Имя поля — из схемы `Order` в OpenAPI           |
| `product_id`       | `sku`                      | Каталожный SKU                                  |
| `unit_price`       | `price`                    | Должен быть согласован с каталогом              |
| `qty`              | `quantity`                 |                                                 |
| `redemption_link`  | `reference_code`         | Ваш UUID v4 — связка с `INT_VOUCHER_REDEEMED`   |
| `delivery_channel` | `delivery_type`          | 0 none / 1 email / 2 SMS / 3 WhatsApp           |
| `delivery_ref`     | `destination`            | В Merkle не класть plaintext; только хэш/факт  |


## Прокси и маппинг SKU (Маркет ↔ ключ прокси ↔ EZ PIN)

В **API Яндекса** в заказе приходит **ваш** SKU (как на витрине: `shopSku` и т.п.). **API прокси** ([Wildflow](https://github.com/vv1ldd/api-wildflow-dev) и аналоги) принимает **тот же** идентификатор как поле **`sku`** в таблицах `catalogs` / `retailer_catalogs` — это **ключ** к строке маппинга и дальше к заказам у EZ PIN (`service_sku` в БД прокси → поле `sku` / `product_code` в запросе к EZ PIN).

Итого по смыслу: **`sku_marketplace` ≈ ключ прокси** (одна строка в бизнесе, если вы не вводите второй внутренний артикул). В журнале всё равно кладём оба имени поля, если в коде ingestion они разведены; иначе в каноне достаточно одного значения в двух ключах или только `sku_internal` с комментарием «= shopSku Маркета» — зафиксировать в `rules_version`.

Для листьев Merkle в канонический `payload` событий (см. [SPEC.md §2.3b](./SPEC.md)) входят как минимум:

| Поле журнала        | Смысл | Пример / источник |
| ------------------- | ----- | ------------------ |
| `sku_internal`      | Ключ в прокси (колонка `catalogs.sku` / `retailer_catalogs.sku`) | Тот же SKU, что вы отдаёте в API партнёрам и видите в заказе МП |
| `sku_marketplace`   | Как в ответе Partner API по заказу | Обычно **то же значение**, что `sku_internal` |
| `sku_supplier`      | `service_sku` → уходит в EZ PIN как `sku` / `product_code` | Из строки каталога прокси |
| `sku_map_version`   | Версия таблицы соответствий | Git SHA / semver / хэш снимка каталога прокси |

Правило: **одна** версия маппинга на момент генерации события; при правке таблицы — новый `sku_map_version`, иначе хэши периода не воспроизводимы.


