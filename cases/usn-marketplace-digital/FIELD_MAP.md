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

Подробно по **исходному коду** Wildflow (без догадок по БД): [docs/integrations/wildflow-proxy-sku-flow.md](../../docs/integrations/wildflow-proxy-sku-flow.md).

Кратко: в репозитории прокси **нет** функции «SKU EZ → SKU Яндекса». Есть только **`catalogs.sku` (ключ партнёра) → `service_sku` → запрос к EZ PIN** (`PartnersController::getServiceSku`). Команды `service:parse-catalog` / `service:parse-retailer-catalog` при первом импорте ставят **`catalogs.sku` = `Str::random()`**; связь с Маркетом достигается **процессом** (вручную в Filament или своим скриптом: выставить `shopSku` = этому `sku`, либо поменять парсер).

**`sku_marketplace`** (например `shopSku` в заказе Маркета) у вас в норме **должен совпасть** с **`catalogs.sku`**, если вы так завели витрину — но это **не выводится** из кода EZ, а задаётся вами.

Для листьев Merkle в канонический `payload` событий (см. [SPEC.md §2.3b](./SPEC.md)) входят как минимум:

| Поле журнала        | Смысл | Пример / источник |
| ------------------- | ----- | ------------------ |
| `sku_internal`      | Колонка `catalogs.sku` / `retailer_catalogs.sku` в прокси | Ключ в API партнёра; после импорта из EZ может быть **случайной** строкой, пока не выровняете под Маркет |
| `sku_marketplace`   | `shopSku` / заказ Маркета | Совпадает с `sku_internal`, если вы так завели оффер |
| `sku_supplier`      | `service_sku` → уходит в EZ PIN как `sku` / `product_code` | Из строки каталога прокси |
| `sku_map_version`   | Версия таблицы соответствий | Git SHA / semver / хэш снимка каталога прокси |

Правило: **одна** версия маппинга на момент генерации события; при правке таблицы — новый `sku_map_version`, иначе хэши периода не воспроизводимы.


