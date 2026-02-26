# Итоговый проект «ValutaTrade Hub», Хлыстиков Валерий М25-555.
# Репозиторий: PYTHON_COURSE_3_1
## Структура проекта

```text
finalproject_Khlystikov_M25-555/
├── data/                    # Хранилище JSON (БД)
│   ├── users.json           # Список пользователей
│   ├── portfolios.json      # Кошельки и активы
│   ├── rates.json           # Кэш последних курсов (Snapshot)
│   └── exchange_rates.json  # История изменений курсов (Журнал)
├── logs/                    # Автоматические логи операций
├── valutatrade_hub/         # Исходный код пакета
│   ├── cli/                 # Интерфейс командной строки
│   ├── core/                # Бизнес-логика (модели, валюты, исключения)
│   ├── infra/               # Инфраструктура (Settings, Database Manager)
│   ├── parser_service/      # Сервис сбора данных из внешних API
│   ├── decorators.py        # Логирование @log_action
│   └── logging_config.py    # Конфигурация ротации логов
├── main.py                  # Точка входа
├── pyproject.toml           # Настройки Poetry и проекта
└── makefile                 # Команды автоматизации
```

## Архитектура и паттерны

Система построена на принципах модульности и включает:
- **Core Service**: Бизнес-логика, модели данных и обработка транзакций.
- **Parser Service**: Изолированный сервис для работы с внешними API.
- **Singleton**: Единые точки доступа к настройкам (`SettingsLoader`) и базе данных (`DatabaseManager`).
- **Decorators**: Автоматическое логирование доменных операций через `@log_action`.
- **Custom Exceptions**: Иерархия собственных исключений для надежной обработки ошибок.

## Команды CLI

### Управление аккаунтом:
* `register --username <name> --password <pass>` — регистрация (начисляется бонус 1000 USD).
* `login --username <name> --password <pass>` — вход в систему.

### Работа с курсами:
* `update-rates` — принудительное обновление данных из внешних API в локальный кэш.
* `show-rates` — показать актуальные курсы из кэша.
* `get-rate --from <CODE> --to <CODE>` — получить курс конкретной пары.

### Торговля и Портфель:
* `buy --currency <CODE> --amount <float>` — покупка валюты за USD из кошелька.
* `sell --currency <CODE> --amount <float>` — продажа валюты (выручка зачисляется в USD).
* `show-portfolio [--base <CODE>]` — общая стоимость всех активов в выбранной валюте (например, в RUB).

## Сборка и запуск проекта

| Команда | Описание |
| :--- | :--- |
| `make install` | Установка зависимостей проекта |
| `make lint` | Проверка кода с помощью ruff |
| `project` | Запуск приложения (команда Poetry) |
| `make build` | Сборка проекта в пакет |
| `make publish` | Публикация пакета |

все JSON-файлы лежат в каталоге data (настраивается data_directory)
rates.json должен быть в data/rates.json
Для обновления фиатных курсов требуется API ключ сервиса ExchangeRate-API.

Получите ключ на https://www.exchangerate-api.com/

Перед запуском приложения установите переменную окружения:

Linux / WSL:

export EXCHANGERATE_API_KEY=your_api_key_here

## Демонстрация asciinema

[asciicast] (https://asciinema.org/a/Gucws1wVxPD5RDTF)
Ссылка на файл записи https://disk.yandex.ru/d/QjH73Wi98S25DQ


---
**Разработчик:** Хлыстиков Валерий 
**Группа:** М25-555  

**Курс:** Программирование на Python (НИЯУ МИФИ)