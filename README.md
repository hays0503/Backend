# YESCADA Backend

REST API сервер системы мониторинга зернохранилищ. Написан на Python/Flask.

## Стек

- Python 3.12, Flask >= 3.0
- SQLite (WAL mode)
- JWT аутентификация (access + refresh токены, HS256)
- Pydantic схемы валидации

## Быстрый старт

```bash
pip install -r requirements.txt
```

### Создание администратора

При первом запуске необходимо создать учётную запись администратора.
Не используйте `admin/admin` — это небезопасно для production.

**Вариант 1 — переменные окружения (рекомендуется для Docker/CI):**

```bash
ADMIN_USERNAME=admin ADMIN_PASSWORD=your-strong-password python run.py
```

Администратор создаётся автоматически при старте, если пользователей ещё нет.

**Вариант 2 — CLI-команда (для ручной установки):**

```bash
flask create-admin
```

Команда интерактивно запросит имя пользователя и пароль.

**Вариант 3 — Python API (для скриптов):**

```python
from app.db import seed_admin
seed_admin("admin", "my-strong-password")
```

`seed_admin()` создаёт администратора только если в БД нет ни одного пользователя.

## API Endpoints

### Auth
| Метод | Путь | Доступ | Описание |
|-------|------|--------|----------|
| POST | `/api/auth/login` | Публичный | Вход, возвращает access + refresh JWT |
| POST | `/api/auth/refresh` | Публичный | Ротация refresh токена |
| GET | `/api/auth/me` | Пользователь | Профиль текущего пользователя |
| PUT | `/api/auth/profile` | Пользователь | Смена имени/пароля |

### Sensor data
| Метод | Путь | Доступ | Описание |
|-------|------|--------|----------|
| POST | `/api/sensor/data` | Публичный | Приём показаний от контроллера |
| GET | `/api/sensor/data` | Пользователь | Последние 100 показаний датчика |
| PUT | `/api/sensor/rename` | Пользователь | Переименовать расположение датчика |
| GET | `/api/device/info` | Пользователь | Список датчиков пользователя со статусом |

### Admin
| Метод | Путь | Доступ | Описание |
|-------|------|--------|----------|
| GET, POST | `/api/admin/users` | Админ | Список/создание пользователей |
| DELETE | `/api/admin/users/:id` | Админ | Удаление пользователя |
| PUT | `/api/admin/users/:id/reset-password` | Админ | Сброс пароля |
| PUT | `/api/admin/users/:id/controllers` | Админ | Назначение контроллеров |
| GET | `/api/admin/controllers` | Админ | Список контроллеров |
| GET | `/api/admin/audit` | Админ | Журнал аудита (пагинация) |

## Конфигурация

Переменные окружения:

- `SECRET_KEY` — секретный ключ JWT (по умолчанию `change-me-in-production-yescada-2026`)
- `ADMIN_USERNAME` — имя первого администратора (создаётся при первом запуске, если пользователей нет)
- `ADMIN_PASSWORD` — пароль первого администратора

Конфигурация в `app/config.py`:
- `ACCESS_TOKEN_EXPIRES_SEC = 3600`
- `REFRESH_TOKEN_EXPIRES_SEC = 604800` (7 дней)
- `KEEP_COUNT_DEFAULT = 1000`
- `CORS_ORIGINS` — разрешённые источники для CORS

## Тестирование

```bash
pytest
pytest tests/          # Unit-тесты
pytest tests/app_test/ # Интеграционные тесты
```

## База данных

6 таблиц: `controllers`, `sensors`, `readings`, `users`, `user_controllers`, `audit_log`.

Автомиграция при запуске — таблицы создаются если не существуют.
