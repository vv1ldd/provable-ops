# Точка.API — выжимка для детерминированного леджера (банк)

Первоисточник: [О сервисе | Точка.API](https://developers.tochka.com/docs/tochka-api/), OpenAPI [Tochka.API](https://developers.tochka.com/docs/tochka-api/api/tochka-api) (версия на момент выгрузки: **v1.90.3-stable**).

Документ — **не** замена официальной доке; при расхождениях верна только документация банка.

---

## 1. Что нужно для нашего кейса (УСН, выплаты маркетплейса, сверка)

| Задача | OAuth scope | Где в доке |
|--------|-------------|------------|
| Список счетов, `accountId` | `ReadAccountsBasic` / `ReadAccountsDetail` | Tochka.API → scopes |
| Остатки (опционально) | `ReadBalances` | idem |
| **Выписка JSON** за период (истина для `BANK_IN` / `BANK_OUT`) | **`ReadStatements`** | [Выписки](https://developers.tochka.com/docs/tochka-api/opisanie-metodov/vypiski) |
| **Мгновенные уведомления** о приходе/расходе | **`ManageWebhookData`** | [Вебхуки](https://developers.tochka.com/docs/tochka-api/opisanie-metodov/vebhuki) |

Аутентификация: **OAuth 2.0** (password flow в описании OpenAPI).

---

## 2. Выписка (основной контур для Merkle)

Официальный сценарий:

1. **Init Statement** — создать запрос выписки по счёту за период: `accountId`, дата начала, дата конца → в ответ **`statementId`**.  
   - Ссылка в доке: [Init Statement](https://developers.tochka.com/docs/tochka-api/api/init-statement-open-banking-v-1-0-statements-post).  
2. **Get Statement** — по `statementId` получить выписку, пока статус не **`Ready`**.  
   - [Get Statement](https://developers.tochka.com/docs/tochka-api/api/get-statement-open-banking-v-1-0-accounts-account-id-statements-statement-id-get).  
3. **Get Statements List** — список доступных выписок.  
   - [Get Statements List](https://developers.tochka.com/docs/tochka-api/api/get-statements-list-open-banking-v-1-0-statements-get).

Особенности (из [Выписки](https://developers.tochka.com/docs/tochka-api/opisanie-metodov/vypiski)):

- Init Statement работает **асинхронно**; в выписке только операции в **финальном** статусе `Ready`.  
- Выписка доступна **24 часа**, затем удаляется.  
- Суммы: **`amount`** (валюта счёта), **`amountNat`** (рубли по курсу ЦБ).  
- Направление: **`creditDebitIndicator`** — `credit` = **приход**, `debit` = **расход**.  
- Иногда вместо «платёжного поручения» встречается **`transactionTypeCode`** = мемориальный ордер — платёж ещё не финально «ушёл»; для актуального статуса запрашивают выписку **повторно**.

### Маппинг → события леджера (`provable-ops`)

| Поле выписки (концепт) | Наш `event_type` | Примечание |
|------------------------|------------------|------------|
| операция с `credit` | `BANK_IN` | В т.ч. **дневная пачка** от маркетплейса — одна строка |
| операция с `debit` | `BANK_OUT` | Оплата поставщику, налоги и т.д. |
| уникальный id операции в JSON выписки | `external_ref = bank:tx:{id}` | Точное имя поля — из OpenAPI / примера ответа |
| `purpose` / назначение | `payload.purpose` | Для мэтча с `MP_PAYOUT` |

Идемпотентность ingestion: пара **`(accountId, bank_operation_id, value_date)`** или то, что банк стабильно отдаёт как уникальный ключ строки.

---

## 3. Вебхуки (ускорение и алерты)

Дока: [Вебхуки](https://developers.tochka.com/docs/tochka-api/opisanie-metodov/vebhuki). Scope: **`ManageWebhookData`**.

Общее:

- POST на ваш URL, тело — **строка JWT**, алгоритм **RS256**, заголовок **`Content-Type: text/plain`**.  
- Проверка подписи: [публичный ключ OpenAPI](https://enter.tochka.com/doc/openapi/static/keys/public).  
- Типы событий, полезные для леджера:  
  - **`incomingPayment`** — входящий платёж (~20 с после зачисления): стороны, **`purpose`**, **`amount`**, **`paymentId`** (тот же id, что в выписке), **`customerCode`**, дата.  
  - **`outgoingPayment`** — исходящий (~20 с).  
  - **`incomingSbpPayment`**, **`incomingSbpB2BPayment`**, **`acquiringInternetPayment`** — если у вас есть СБП/эквайринг (для полноты картины денег).

Вебхук **не заменяет** выписку как «снимок за период» для Merkle, но даёт **раннее событие** и помогает ловить расхождения (вебхук есть, в выписке нет / наоборот).

---

## 4. Сверка с маркетплейсом (напоминание)

Одна **`BANK_IN`** за день = сумма многих заказов Яндекса → в леджере мэтчится с **агрегатом** `MP_PAYOUT` и списком `order_id` из API маркетплейса (см. `cases/usn-marketplace-digital/SPEC.md` §5.4). Поле **`purpose`** в выписке Точки часто критично для привязки к реестру выплаты.

---

## 5. PDF

Официальный сайт — **динамический**; готового одного PDF от Точки под рукой нет. Варианты:

- **Печать в PDF из браузера**: открыть нужные страницы доки → Печать → «Сохранить как PDF».  
- Локально из этого файла: `pandoc docs/integrations/tochka-api-for-ledger.md -o tochka-ledger.pdf` (если установлен Pandoc + движок PDF).

Рабочий формат для репозитория — **этот Markdown**: его можно версионировать вместе с `rules_version` и диффить при изменениях API.
