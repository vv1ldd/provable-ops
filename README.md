# provable-ops

Концепция платформы: **выгрузки 1С + банковские данные** → канонизация → журнал событий → Merkle/commitment и сверка «учёт ↔ деньги».

Подробнее в [WHITEPAPER.md](./WHITEPAPER.md).

### Кейсы

- [УСН «доходы» + маркетплейс + цифровой поставщик](./cases/usn-marketplace-digital/README.md) — первый детерминированный журнал на трёх API.

### Интеграции (выжимки под леджер)

- [Точка.API — выписки, вебхуки, scopes](./docs/integrations/tochka-api-for-ledger.md)
- [Яндекс Маркет Partner API — заказы, отчёты, уведомления](./docs/integrations/yandex-market-api-for-ledger.md)
- [EZ PIN / EZPayPin API — цифровые карты (поставщик)](./docs/integrations/ezpaypin-api-for-ledger.md)
- [Wildflow — как по коду `sku` прокси ↔ `service_sku` EZ (и почему это не «SKU Маркета из EZ»)](./docs/integrations/wildflow-proxy-sku-flow.md)

### Проверка доступа к API

Скрипт без зависимостей: [scripts/ingestion/smoke_fetch.py](./scripts/ingestion/smoke_fetch.py) — `all`: OAuth Точки (или готовый токен) и счета, заказы Маркета за 7 дней, EZ PIN баланс + заказы; `ledger`: то же плюс **выписка** Точки (`TOCHKA_ACCOUNT_ID`), **отчёт по платежам** united-netting (скачивание в `scripts/ingestion/out/`), опционально каталог EZ PIN. Шаблон: [scripts/ingestion/.env.example](./scripts/ingestion/.env.example).
