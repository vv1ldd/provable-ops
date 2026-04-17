# provable-ops

Концепция платформы: **выгрузки 1С + банковские данные** → канонизация → журнал событий → Merkle/commitment и сверка «учёт ↔ деньги».

Подробнее в [WHITEPAPER.md](./WHITEPAPER.md).

### Кейсы

- [УСН «доходы» + маркетплейс + цифровой поставщик](./cases/usn-marketplace-digital/README.md) — первый детерминированный журнал на трёх API.

### Интеграции (выжимки под леджер)

- [Точка.API — выписки, вебхуки, scopes](./docs/integrations/tochka-api-for-ledger.md)
- [Яндекс Маркет Partner API — заказы, отчёты, уведомления](./docs/integrations/yandex-market-api-for-ledger.md)

PDF из этих файлов (локально, после `brew install pandoc tectonic`): `./scripts/md-to-pdf.sh` — результат в `docs/integrations/*.pdf` (в git не коммитится).

