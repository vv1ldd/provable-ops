# EZ PIN / EZPayPin API — выжимка для детерминированного леджера (поставщик)

Это **API поставщика цифровых карт** в вашем флоу (после обмена ваучера), **не** Яндекс Маркет.

Первоисточники:

- [Документация панели](https://panel.ezpaypin.com/docs/index.html)  
- [SwaggerHub EZPin Access API v2.0.2](https://app.swaggerhub.com/apis-docs/ezpin/EZPin_Access_API/v2.0.2)  
- OpenAPI JSON: `https://api.swaggerhub.com/apis/ezpin/EZPin_Access_API/v2.0.2`

Полная выжимка по полям из OpenAPI у вас может лежать отдельным файлом `ezpaypin-openapi-v2.0.2-reference.md` рядом с проектом.

---

## 1. Базовый URL и безопасность

Из OpenAPI v2.0.2 (прод):

- **`https://api.ezpaypin.com/vendors/v2`** — base path для запросов (не mock SwaggerHub).

**Аутентификация:**

1. **POST** `/auth/token/` — тело: `client_id`, `secret_key` → ответ с **`access`** (JWT) и сроком.  
2. Дальше: заголовок **`Authorization: Bearer {access}`** (`bearerAuth`).

---

## 2. Эндпоинты, важные для леджера

| Задача | Метод | Заметки для журнала |
|--------|--------|----------------------|
| Баланс перед/после заказа | **GET** `/balance/` | Массив валют/сумм — контроль «хватило ли средств» |
| Каталог / цена | **GET** каталога (см. OpenAPI) | Для согласованности `sku` + `price` с заказом |
| **Создать заказ цифровых карт** | **POST** `/orders/` | Тело: `sku`, `quantity`, `price`, `delivery_type` (0 none / 1 email / 2 SMS / 3 WhatsApp), `destination`, опционально `terminal_id` / `terminal_pin`, **`reference_code`** — **UUID v4**, обязателен |
| История заказов | **GET** `/orders/` | `limit`, `offset`, `start_date`, `end_date` |
| Детали заказа | **GET** `/orders/{reference_code}/` | Тот же `reference_code`, что вы сгенерировали |
| Карты в заказе | **GET** `/orders/{reference_code}/cards/` | Номера/данные карт — **не класть в публичный Merkle**; хэшировать или исключить по политике |
| Уведомления на ваш URL | **GET/POST** `/notification_config/` | Настройка webhook для статусов (см. OpenAPI) |

Ошибки: **400** с `detail` + `code`; **401** при истёкшем токене; **406** на `POST /orders/` — PIN/терминал (код **617** в примерах).

---

## 3. Маппинг на события `provable-ops`

| Действие | `event_type` | `external_ref` / payload |
|----------|--------------|---------------------------|
| Успешный **POST** `/orders/` | `SUP_PURCHASE` | `sup:order:{reference_code}`; в payload: `sku`, `quantity`, `price`, `delivery_type`, **без** полного `destination` в публичном слое |
| Ответ 200 с id заказа EZ | то же событие, обновление | добавить `supplier_order_id` если поле есть в ответе |
| **GET** деталей/карт | опционально `SUP_PURCHASE_DETAIL` | или расширить payload внутренним контуром |
| Ваш бэкенд отправил email | `INT_GIFT_EMAIL_SENT` | связь по `reference_code` = ваш `redemption_id` / `voucher_id` |

Связка с маркетплейсом: **`reference_code`** (или ваш внутренний id) должен совпадать с тем, что вы записали при **`INT_VOUCHER_REDEEMED`**.

---

## 4. Прокси и маппинг SKU (Маркет ↔ вы ↔ EZ PIN)

Если клиентский код **не бьётся напрямую** в `api.ezpaypin.com`, а ходит в **ваш прокси**, то:

- в EZ PIN уходит уже **их** `sku` из каталога поставщика (**`sku_supplier`** в терминологии кейса);  
- на Маркете у того же товара другой идентификатор (**`sku_marketplace`**);  
- в учёте у вас **`sku_internal`** и таблица соответствий с версией **`sku_map_version`**.

Для Merkle/commitment в `SUP_PURCHASE` (и в связанных `MP_ORDER` / internal) в **`payload_canonical`** должны входить **`sku_internal`**, **`sku_map_version`**, **`sku_supplier`**; **`sku_marketplace`** — если известен из заказа Маркета. Сырой URL прокси и секреты в канон не включаются. Подробнее: [cases/usn-marketplace-digital/SPEC.md](../../cases/usn-marketplace-digital/SPEC.md) §2.3b и [FIELD_MAP.md](../../cases/usn-marketplace-digital/FIELD_MAP.md).

---

## 5. Идемпотентность и детерминизм

- **`reference_code`**: генерируете **один раз** на попытку покупки; повторный POST с тем же кодом должен трактоваться как **тот же запрос** (проверить по доке/поведению API — при необходимости фиксируется в `rules_version`).  
- В журнал кладёте **канонический JSON** ответа 200 (без секретов карт) + UTC `ingested_at`.  
- Токен обновления: отдельное событие `SUP_AUTH` не обязательно; достаточно логов ingestion вне Merkle или редких корней «только операции».

---

## 6. Сверка с банком

Списание у поставщика в **банке** (Точка) мэчится по сумме/дате/назначению с **`BANK_OUT`**, если оплата идёт с расчётного счёта; если списание с **предоплаченного баланса EZ** — в банке может не быть строки на каждый заказ — тогда правило в `rules_version`: «источник истины по поставщику — API EZ + баланс».

---

*Версия выжимки: ezpaypin-ledger-0.2.0 (прокси + SKU; править при смене OpenAPI).*
