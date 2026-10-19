# ProBook

Backend (FastAPI) для бронирования переговорных комнат и коворкингов, организации событий и модерации заявок; вход через Microsoft-аккаунт организации.

## Быстрый старт

```bash
git clone https://github.com/Shoker2/Probook.git
cd Probook
docker compose up -d --build   # первый запуск создаст config.ini с настройками по умолчанию
```

API будет на http://localhost:8001/api (контейнер слушает 8000, наружу проброшен 8001).
Swagger/ReDoc/OpenAPI **отключены** (`docs_url=None, openapi_url=None` в [main.py](main.py)); чтобы включить `/docs`, уберите эти параметры.

Миграции (`alembic upgrade head`) применяются автоматически при старте контейнера.

## Пример

Почти все эндпоинты требуют заголовок `Authorization` с JWT, который выдаёт сам сервис после входа через Microsoft:

```bash
# 1. URL для входа через Microsoft (откройте его в браузере)
curl "localhost:8001/api/auth/microsoft/get_authorization_url"

# 2. После редиректа обменяйте code на токен сервиса
curl "localhost:8001/api/auth/microsoft/token?code=<CODE>"
# -> {"token": "<JWT>"}

# 3. Список комнат
curl localhost:8001/api/rooms/ -H "Authorization: <JWT>"
```

Ответы авторизованных запросов обёрнуты в `{"new_token": ..., "result": ...}`: если Microsoft-токен был обновлён, в `new_token` придёт новый JWT, его нужно сохранить.

## Как устроено

```
клиент ──► FastAPI (main.py, префикс /api)
             ├─ routers/*      эндпоинты: auth, rooms, items, events, coworkings,
             │                 schedule, groups, permissions, img, workers, action_history
             ├─ auth/          JWT + Microsoft OAuth (httpx-oauth), автообновление токена
             ├─ permissions/   проверка прав группы пользователя
             ├─ models_/       таблицы SQLAlchemy Core  ──► PostgreSQL (asyncpg, alembic)
             └─ services/      фоновые задачи (asyncio в lifespan) ──► Redis
```

- **Авторизация.** Пароли не хранятся: пользователь входит через Microsoft, сервис выпускает свой JWT (HS256), внутри которого лежат UUID пользователя и Microsoft access/refresh-токены; срок жизни JWT равен сроку жизни Microsoft-токена. Когда JWT истёк, `get_current_user` сам обновляет его через refresh-токен, а middleware добавляет новый токен в `new_token` ответа. Так клиенту не нужен отдельный refresh-эндпоинт.
- **Права.** У пользователя есть группа со списком прав вида `rooms.create`, `event.moderate` (полный перечень в [permissions/permissions.py](permissions/permissions.py)). Поддерживаются `*` и отрицание через `!`. Суперпользователь может всё. Группа по умолчанию (`is_default`) назначается тем, у кого группы нет.
- **События и бронирование.** События и коворкинг-брони (`personal_reservation`) создаются со статусом «не промодерировано», модератор одобряет или отклоняет (с причиной). Пересечения по комнате и времени отклоняются. Повторяющиеся события хранятся как набор отдельных записей с общим `event_base_id`; фоновая задача раз в сутки дозаполняет их вперёд.
- **Расписание.** Рабочие слоты комнаты задаются шаблоном по дням недели (даты `01.01.1000`–`07.01.1000` в `schedule`) и могут переопределяться на конкретную дату.
- **Картинки.** Загруженный файл лежит в `static/img` и отдаётся по `/api/static`. Аватарки пользователей из Microsoft кэшируются во временные файлы; Redis с `notify-keyspace-events Ex` сообщает об истечении ключа, и [services/tmp_image_remover.py](services/tmp_image_remover.py) удаляет файл. Поэтому Redis должен быть запущен с этой опцией (в `compose.yaml` она уже есть).
- **Аудит.** Изменения пишутся в `action_history` и читаются через `/api/history`.

## Конфигурация

Настройки читаются из `config.ini` в корне (файл в `.gitignore`; если его нет, создаётся при первом запуске со значениями по умолчанию). `.env` не используется.

| Секция.ключ | Назначение | Пример |
|---|---|---|
| `Database.db_host` | хост PostgreSQL | `db` |
| `Database.db_port` | порт PostgreSQL | `5432` |
| `Database.db_name` | имя БД | `probook` |
| `Database.db_user` | пользователь БД | `postgres` |
| `Database.db_pass` | пароль БД; должен совпадать с `POSTGRES_PASSWORD` в [compose.yaml](compose.yaml) | `change-me` |
| `Redis.host` / `port` | адрес Redis | `redis` / `6379` |
| `Redis.login` / `password` | учётные данные Redis (по умолчанию пусто) | |
| `Miscellaneous.secret` | ключ подписи JWT и имён файлов; **обязателен**, без него токены небезопасны | длинная случайная строка |
| `Miscellaneous.min_available_day_booking` | через сколько дней от сегодня можно бронировать | `2` |
| `Miscellaneous.max_available_day_booking` | на сколько дней вперёд можно бронировать | `60` |
| `Microsoft.client_id` | ID приложения в Azure AD | `0e7132d1-...` |
| `Microsoft.client_secret` | секрет приложения | |
| `Microsoft.tenant_id` | тенант Azure AD | `19ba435d-...` |
| `Microsoft.redirect_url` | redirect URI, зарегистрированный в Azure | `http://localhost:3000/sign-in` |

Прочее: часовой пояс (`TZ=Europe/Moscow`) и пароль Postgres заданы прямо в [compose.yaml](compose.yaml); список CORS-origins — в [main.py](main.py).

## Разработка

Локально без Docker (нужны PostgreSQL и Redis с `notify-keyspace-events Ex`, адреса укажите в `config.ini`):

```bash
python -m venv venv && venv\Scripts\activate      # Windows
pip install -r requirements.txt
python -m alembic upgrade head
python main.py                                    # uvicorn с reload на :8000
```

Миграции:

```bash
python -m alembic revision --autogenerate -m "описание"
python -m alembic upgrade head
python -m alembic downgrade -1
```
