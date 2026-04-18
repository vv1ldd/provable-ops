# Wildflow + Marketplace — как по коду связаны EZ PIN, прокси и `offerId` Яндекса

Репозитории:

- [vv1ldd/api-wildflow-dev](https://github.com/vv1ldd/api-wildflow-dev) — прокси EZ PIN (`catalogs` / `retailer_catalogs`).  
- [vv1ldd/marketplace](https://github.com/vv1ldd/marketplace) — импорт каталога с **продакшен** API `api.wildflow.dev`, **генерация** строки для поля **`offerId`** / `shopSku` в Яндекс Маркете и выгрузка офферов (`Ym\MainController::sendItemsWildflow`).

В `api-wildflow-dev` **нет** вызовов Partner API Яндекса. Генерация человекочитаемого SKU для Маркета живёт в **`marketplace`** (`WildflowParser::skuGenerator`).

---

## 1. Направление данных в runtime (`PartnersController`)

Партнёр шлёт в прокси **`sku`** (строка) + **`type`**: `catalog` | `retailer_catalog`.

- При **`catalog`**: `Catalog::where('sku', $sku)->value('service_sku')` → в EZ PIN уходит это значение как **`sku`** (integer) в `CreateOrderRequest`.  
- При **`retailer_catalog`**: в коде сейчас `Partners::where('sku', $sku)` — у модели `partners` в миграции **нет** колонки `sku`; для retailer ожидаемо нужен **`RetailerCatalog`**.

Источник: `app/Http/Controllers/PartnersController.php` — методы `checkAvailability`, `createOrder`, приватный `getServiceSku`.

**Итог:** запрос партнёра индексируется по **`catalogs.sku`** / **`retailer_catalogs.sku`**; в EZ уходит **`service_sku`** из той же строки.

---

## 2. Как строки каталога появляются из API EZ PIN (команды парсинга)

### `service:parse-catalog`

- Читает каталог EZ: `$client->getCatalog()`, перебирает `$data['results']`.  
- Для каждого `$item['sku']` (SKU **у поставщика**):  
  - `firstOrCreate` по **`service_sku` = $item['sku']`**,  
  - при создании **`sku` = `Str::random()`** — случайная строка, **не** из Маркета и **не** из EZ как «витринный» артикул.

Источник: `app/Console/Commands/ParseCatalog.php`.

### `service:parse-retailer-catalog`

- Аналогично: ключ **`service_sku` = $item['product_code']`**, новый **`sku` = `Str::random()`**.

Источник: `app/Console/Commands/ParseRetailerCatalog.php`.

**Итог по коду:** стабильная связь с API источника (EZ) — поле **`service_sku`** в БД прокси. Поле **`sku`** в БД — **ключ для партнёрского API**; после парсинга оно **случайное**, пока вы не перезапишите его в Filament. **Если офферы в Яндекс грузите через репозиторий `marketplace`**, на витрину уходит **не** этот `sku`, а строка из `skuGenerator` (см. §3).

---

## 3. Репозиторий `marketplace`: ответ Wildflow → строка для Яндекса

Команда **`app:wildflow-parser`** (по расписанию hourly в `routes/console.php`) дергает продакшен:

`GET https://api.wildflow.dev/api/v1/partners/catalog?type=retailer_catalog|catalog`

и делает `WildflowCatalog::upsert` в таблицу **`wildflow_catalogs`**.

**Важно про имена колонок в БД `marketplace` (они путают с EZ):**

| Колонка `wildflow_catalogs` | Что кладёт код | Соответствие `api-wildflow-dev` |
|----------------------------|----------------|----------------------------------|
| **`service_sku`** | `$item['sku']` из JSON ответа Wildflow | Это **`sku` партнёра** в прокси (`catalogs.sku`), **не** числовой SKU EZ в смысле колонки `service_sku` Wildflow |
| **`sku`** | `skuGenerator($data, $type)` | **Идентификатор оффера для Яндекса** (`offerId` / фактический `shopSku` в потоке Маркета) |

`skuGenerator` (файл `app/Console/Commands/WildflowParser.php`):

- **`retailer_catalog`:** `VOUCHER-GC-{нормализованный_title}-{region}-{price}{currency}-RTL-{product.sku}`  
- **`catalog`:** `VOUCHER-GC-{title}-{region}-{max_price}{currency}-CTLG-{data.sku}`  

То есть в строку для Маркета **вшиваются** поля из **`data`** (ответ/кэш каталога EZ: валюта, регион, числовой `sku` товара у поставщика и т.д.) + **ключ партнёра** хранится отдельно в колонке с именем `service_sku`.

Импорт офферов в Маркет: `Ym\MainController::sendItemsWildflow` — в теле импорта **`"offerId" => $item->sku`**, т.е. в Яндекс уходит **сгенерированная** строка `VOUCHER-GC-…`, а не случайный `Str::random()` из прокси.

---

## 4. Сводная таблица «кто что называет sku»

| Смысл для леджера | `api-wildflow-dev` | `marketplace.wildflow_catalogs` | Яндекс Partner API |
|-------------------|--------------------|----------------------------------|----------------------|
| Ключ вызова прокси / партнёра | `catalogs.sku` | колонка **`service_sku`** (хранит `item['sku']` из API) | — |
| SKU в заказе / оффере Маркета | — | колонка **`sku`** (`skuGenerator`) | `shopSku` / `offerId` |
| SKU у EZ в `POST /orders/` | `catalogs.service_sku` | внутри `data` (напр. `product.sku`, `product_code`) | — |

Заказ Маркета по позиции ссылается на **`sku` из п.2** (строка `VOUCHER-GC-…`). Заказ у поставщика через прокси — по **`catalogs.sku`**, который в `marketplace` лежит в колонке **`service_sku`**.

---

## 5. Для леджера `provable-ops`

- **`sku_marketplace`:** значение из заказа Маркета = обычно строка **`VOUCHER-GC-…`** из `marketplace.wildflow_catalogs.sku`.  
- **`sku_internal` / ключ прокси:** `marketplace.wildflow_catalogs.service_sku` = `api-wildflow-dev.catalogs.sku` (партнёрский ключ).  
- **`sku_supplier`:** числовой/строковый идентификатор EZ из данных каталога и маппинга прокси (`api-wildflow-dev.catalogs.service_sku` → поле в запросе к EZ).  
- **`sku_map_version`:** версия снимка **`wildflow_catalogs`** + версия каталога прокси (или хэш строки `skuGenerator` при смене правил).

## 6. HTTP API леджера на стороне `marketplace`

В [vv1ldd/marketplace](https://github.com/vv1ldd/marketplace) добавлены read-only эндпоинты (тот же Bearer-токен `ApiApplication`, что и у `/api/redeem/*`):

- **`GET /api/ledger/catalog-map`** — снимок маппинга `sku_marketplace` / `sku_proxy_key` / `sku_supplier` + версия строки.  
- **`GET /api/ledger/redeem-events`** — пагинация по `order_items` с флагами redeem/activate и безопасным контактом (без паролей из `client_info`).

Описание параметров: [marketplace/docs/LEDGER_API.md](https://github.com/vv1ldd/marketplace/blob/master/docs/LEDGER_API.md).

*Документ: wildflow-sku-flow-0.3.0 (добавлен Ledger HTTP API на marketplace).*
