# Wildflow (`api-wildflow-dev`) — как по коду связаны SKU EZ PIN и запрос партнёра

Репозиторий: [vv1ldd/api-wildflow-dev](https://github.com/vv1ldd/api-wildflow-dev). В нём **нет** вызовов API Яндекс Маркета и **нет** функции «перевести SKU источника в SKU маркетплейса». Связка с Маркетом — **внешний процесс** (вы заводите `shopSku` = тому `sku`, под которым строка лежит в прокси).

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

**Итог по коду:** стабильная связь с API источника (EZ) — поле **`service_sku`** в БД прокси. Поле **`sku`** в БД — **ключ для партнёрского API**; после парсинга оно **случайное**, пока вы не перезапишите его (например в Filament: `CatalogResource` / `RetailerCatalogResource`) на **`shopSku`**, который вы завели на Маркете.

---

## 3. Что это значит для «SKU маркетплейса»

| Смысл | Где живёт | Как совпадает с Маркетом |
|--------|-----------|---------------------------|
| SKU в заказе Яндекса (`shopSku`) | Partner API Маркета | Должен **вручную/процессом** совпасть с **`catalogs.sku`**, если вы хотите без второй таблицы |
| SKU в запросе к прокси | тело `sku` у партнёра | = `catalogs.sku` |
| SKU у EZ в заказе | `service_sku` в БД → поле в запросе к EZ | = `item['sku']` / `product_code` из каталога EZ |

Автоматического преобразования «EZ → Яндекс» в репозитории **нет**; есть только **«ваш sku строки каталога → service_sku → EZ»**.

---

## 4. Для леджера `provable-ops`

- В событиях храните **`sku_supplier`** (= `service_sku`), **`sku_internal`** (= `catalogs.sku` = ключ партнёра и, при вашем процессе, = `shopSku`), **`sku_map_version`**.  
- Если меняете `catalogs.sku` в админке под Маркет — версионируйте снимок каталога.

*Документ: wildflow-sku-flow-0.1.0 (по состоянию кода на просмотр репозитория).*
