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
| `sku_marketplace`   | `shopSku` / offer / позиция заказа          | Как в карточке и заказе Маркета               |


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


## Прокси и маппинг SKU (Маркет ↔ внутренний ↔ EZ PIN)

Запросы к EZ PIN идут через **ваш прокси**, который переводит **внутренний SKU** в **`sku` каталога EZ PIN**; тот же товар на Маркете идёт под **`sku_marketplace`**. Для листьев Merkle в канонический `payload` событий (см. [SPEC.md §2.3b](./SPEC.md)) входят как минимум:

| Поле журнала        | Смысл | Пример / источник |
| ------------------- | ----- | ------------------ |
| `sku_internal`      | Ваш ключ товара в учёте и в прокси | Конфиг / БД |
| `sku_marketplace`   | Идентификатор в потоке Маркета | Строка из заказа / оффера |
| `sku_supplier`      | Значение поля `sku` в `POST /orders/` EZ PIN | То, что прокси реально отправил |
| `sku_map_version`   | Версия таблицы соответствий | Git SHA файла маппинга, semver, ULID релиза |

Правило: **одна** версия маппинга на момент генерации события; при правке таблицы — новый `sku_map_version`, иначе хэши периода не воспроизводимы.


