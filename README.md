# C2C Order Grabber Bot

Telegram-бот для автоматического мониторинга и захвата ордеров на платформе Cards2Cards с AWS Cognito авторизацией.

> Fork оригинального проекта [Ps1nu5/c2c-order-grabber](https://github.com/Ps1nu5/c2c-order-grabber) с улучшениями производительности, мониторингом и автоматическим деплоем в AWS Lightsail.

## ⚡ Основные возможности

### Функциональность
- ✅ Мониторинг новых заказов в реальном времени
- ✅ Настраиваемые фильтры по сумме (мин/макс)
- ✅ Автоматическая AWS Cognito авторизация с MFA
- ✅ Поддержка прокси для обхода IP-блокировок
- ✅ SQLite база данных для настроек и логов
- ✅ Обход CloudFront WAF через curl_cffi
- ✅ Уведомления о взятых и пропущенных заказах

### Производительность и надёжность
- ⚡ **Оптимизация латентности:**
  - Переиспользование HTTP-соединений (Keep-Alive 30s)
  - DNS кеширование (10 минут)
  - TCP_NODELAY для минимальной задержки
  - Connection pooling (до 20 соединений)

- 🔄 **Адаптивный polling:**
  - Базовый интервал: 0.5 секунды (с jitter ±20%)
  - Автоматическое удвоение при rate limit (429)
  - Плавное восстановление (95% × интервал)
  - Cap 5 секунд для защиты API

- 🛡️ **Надёжность:**
  - Idempotency-Key для предотвращения дублей при таймаутах
  - Retry логика: 3 попытки с linear backoff (0.3s × attempt)
  - Docker HEALTHCHECK (проверка каждые 30s)
  - Автоматический перезапуск при падении

### Мониторинг (Prometheus + Grafana)
- 📊 **Comprehensive dashboard** с 10 панелями:
  - Active Sessions, Orders Seen Rate, Success Rate
  - Poll Latency (p50/p95/p99), Order Outcomes
  - Time to Grab (detection → success), Queue Depth
  - Rate Limits, API Requests breakdown

- 📈 **Метрики:**
  - **Counters:** orders_seen/taken/failed, api_requests, poll_cycles, rate_limits
  - **Gauges:** active_sessions, queue_depth, current_poll_interval
  - **Histograms:** poll_duration, order_grab_duration, time_to_grab

- 🔍 **Production-ready:**
  - All-in-one контейнер (Bot + Prometheus + Grafana)
  - История метрик 7 дней
  - HTTPS доступ к Grafana из любой точки мира
  - ~250-300MB RAM (влезает в Lightsail small $10/мес)

## 📋 Требования

- Python 3.10+
- Telegram Bot Token (получить у [@BotFather](https://t.me/botfather))
- Учётные данные Cards2Cards

## 🚀 Локальная установка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/DASHULYA1337/c2c-order-grabber.git
cd c2c-order-grabber
```

### 2. Создать виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения

Скопировать `.env.example` в `.env` и настроить:

```bash
cp .env.example .env
```

Отредактировать `.env`:

```env
# Обязательно
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_telegram_chat_id_here

# Опционально: код-приглашение для контроля доступа
INVITE_CODE=your_secret_invite_code

# AWS Cognito (можно оставить как есть)
AWS_REGION=us-east-1
COGNITO_CLIENT_ID=6eio0hlq4tmr2o9d30ht9cvfn7
COGNITO_USER_POOL_ID=us-east-1_9szPtqd8w
COGNITO_IDENTITY_POOL_ID=us-east-1:db254d71-fe90-4631-bee5-d7ed0a489588
```

### 5. Запустить бота

```bash
python main.py
```

## 🎯 Использование

1. Запустить бота командой `/start` в Telegram
2. Ввести invite code (если настроен)
3. Ввести учётные данные Cards2Cards
4. Настроить фильтры по сумме (опционально)
5. Начать мониторинг

### Команды бота

- `/start` - Запустить бота / авторизоваться
- `/stop` - Остановить мониторинг
- `/settings` - Настроить фильтры
- `/status` - Посмотреть статистику

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Обязательна | Описание | По умолчанию |
|------------|-------------|----------|--------------|
| `TELEGRAM_BOT_TOKEN` | Да | Telegram bot token | - |
| `ADMIN_CHAT_ID` | Да | ID чата администратора | - |
| `INVITE_CODE` | Нет | Код-приглашение | - |
| `AWS_REGION` | Нет | AWS регион | `us-east-1` |
| `DATABASE_URL` | Нет | URL базы данных | `sqlite+aiosqlite:///./data/bot.db` |
| `LOG_FILE` | Нет | Путь к лог-файлу | `bot.log` |
| `POLL_INTERVAL_S` | Нет | Интервал опроса (секунды) | `0.5` |
| `DEBUG` | Нет | Режим отладки | `false` |
| `HTTP_PROXY` | Нет | HTTP прокси | - |
| `HTTPS_PROXY` | Нет | HTTPS прокси | - |

### Настройка прокси

Для обхода блокировок по IP настройте прокси:

```env
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080
# Поддерживаются SOCKS5 прокси
```

## 🐳 Docker (локальная разработка с мониторингом)

### Запуск всего стека (Bot + Prometheus + Grafana)

```bash
docker-compose up -d
```

**Доступ к сервисам:**
- Bot health check: http://localhost:8080/health
- Bot metrics: http://localhost:9090/metrics
- Prometheus UI: http://localhost:9091
- **Grafana Dashboard: http://localhost:3000** (admin/admin)

### Просмотр логов

```bash
docker-compose logs -f bot
docker-compose logs -f prometheus
docker-compose logs -f grafana
```

### Остановка

```bash
docker-compose down
```

## ☁️ Production деплой (AWS Lightsail)

Автоматический деплой с Terraform и GitHub Actions.

### Что деплоится

**All-in-one контейнер** (`Dockerfile.production`):
- Bot (Python app) - порты 8080 (health), 9090 (metrics)
- Prometheus - порт 9091 (scraping метрик, retention 7 дней)
- Grafana - порт 3000 (HTTPS публичный доступ)

Всё управляется через **supervisord** - автоматический перезапуск при падении.

### Быстрый старт

#### 1. Настроить GitHub Secrets

В Settings → Secrets and variables → Actions добавить:

```
AWS_ACCESS_KEY_ID          # AWS credentials
AWS_SECRET_ACCESS_KEY      # AWS credentials
TELEGRAM_BOT_TOKEN         # Токен бота
ADMIN_CHAT_ID              # ID чата админа
INVITE_CODE                # (опционально)
DOCKERHUB_USERNAME         # Docker Hub username
DOCKERHUB_TOKEN            # Docker Hub token
HTTP_PROXY                 # (опционально)
HTTPS_PROXY                # (опционально)
```

#### 2. Задеплоить инфраструктуру

```bash
cd deploy/terraform
terraform init
terraform apply
```

#### 3. Автоматический деплой

```bash
git push origin main
```

GitHub Actions автоматически:
- Соберёт production image
- Push в Docker Hub
- Задеплоит в AWS Lightsail
- Expose Grafana на HTTPS

#### 4. Получить URL Grafana

```bash
aws lightsail get-container-services \
  --service-name c2c-order-grabber \
  --region eu-north-1 \
  --query 'containerServices[0].url' \
  --output text
```

Результат: `https://c2c-order-grabber.xxxxx.eu-north-1.cs.amazonlightsail.com`

Открыть в браузере, логин: `admin` / `admin` ⚠️ **Сменить пароль сразу!**

### Стоимость

| Размер | vCPU | RAM | Цена/мес | Рекомендация |
|--------|------|-----|----------|--------------|
| micro | 0.25 | 512MB | $7 | ❌ Мало (OOM) |
| **small** | 0.5 | **1GB** | **$10** | ✅ **Оптимально** |
| medium | 1.0 | 2GB | $20 | ✅ Комфортно (много юзеров) |
| large | 2.0 | 4GB | $40 | ⚠️ Избыточно |

**Footprint:** ~250-330MB RAM → влезает в small с запасом.

## 📊 Архитектура

### Producer-Consumer Pattern

```
OrderMonitor (Producer)
    ↓ (обнаружил новый заказ)
asyncio.Queue
    ↓ (FIFO)
OrderProcessor (Consumer)
    ↓ (попытка взять заказ)
API: POST /orders/{slug}/take
    ↓
Callbacks (on_taken / on_failed)
```

### Ключевые паттерны

- **Per-user session isolation** - у каждого пользователя свои credentials и monitoring
- **Adaptive polling с jitter** - защита от детекта бота
- **Credential auto-refresh** - токены обновляются за ~1 час до истечения
- **WAF bypass** - CloudFront обход через curl_cffi с Chrome impersonation
- **Callback-based notifications** - чистое разделение слоёв

### Структура проекта

```
c2c-order-grabber/
├── main.py              # Точка входа
├── app.py               # Главный класс приложения
├── config.py            # Конфигурация
├── cognito_auth.py      # AWS Cognito авторизация
├── api_client.py        # Cards2Cards API клиент
├── aws_signer.py        # AWS Signature V4
├── user_session.py      # Управление сессиями пользователей
├── monitor.py           # Мониторинг заказов
├── processor.py         # Обработка заказов
├── metrics.py           # Prometheus метрики
├── bot/                 # Telegram бот
│   ├── handlers/        # Обработчики команд
│   │   ├── auth.py      # Авторизация
│   │   ├── control.py   # Управление (start/stop)
│   │   ├── settings.py  # Настройки фильтров
│   │   └── main_menu.py # Главное меню
│   └── keyboards.py     # Клавиатуры
├── db/                  # База данных
│   ├── engine.py        # SQLAlchemy engine
│   ├── models.py        # Модели данных
│   └── repository.py    # Репозитории
├── deploy/              # Деплой
│   └── terraform/       # Infrastructure as Code
├── benchmark/           # RTT тестирование
│   ├── measure_rtt.py   # Измерение латентности
│   └── deploy_benchmark.sh # Multi-region деплой
├── monitoring/          # Конфигурация мониторинга
│   ├── prometheus.yml
│   └── grafana/
│       ├── provisioning/
│       └── dashboards/
├── Dockerfile           # Development образ
├── Dockerfile.production # Production all-in-one
├── docker-compose.yml   # Локальный стек
└── requirements.txt     # Зависимости
```

## 🔬 Benchmark инструменты

### Измерение RTT из разных AWS регионов

Используется для выбора оптимального региона деплоя:

```bash
cd benchmark
./deploy_benchmark.sh
```

Автоматически:
1. Деплоит контейнеры в 7 AWS регионов
2. Измеряет DNS, TCP, TLS, HTTP латентность
3. Генерирует сравнительную таблицу
4. Рекомендует лучший регион

**Пример вывода:**
```
Region                RTT (ms)   TCP (ms)   TLS (ms)  HTTP (ms)
--------------------------------------------------------------
us-east-1                4.2ms      4.3ms      9.1ms     15.7ms  ← BEST
eu-west-1               92.3ms     93.7ms    185.1ms    241.8ms
eu-north-1             118.4ms    119.1ms    234.7ms    298.2ms
```

## 🛡️ Безопасность

- Никогда не коммитить `.env` файл в git
- Использовать сильные invite codes
- Надёжно хранить приватные ключи
- Регулярно обновлять зависимости
- Сменить дефолтный пароль Grafana (`admin`)

## 🔧 Технологии

### Runtime & Frameworks
- [Python 3.11](https://www.python.org/) - Runtime
- [aiogram 3.7+](https://github.com/aiogram/aiogram) - Telegram Bot Framework (async)
- [aiohttp 3.9+](https://github.com/aio-libs/aiohttp) - Async HTTP клиент

### Database & ORM
- [SQLAlchemy 2.0+](https://www.sqlalchemy.org/) - Async ORM
- [aiosqlite](https://github.com/omnilib/aiosqlite) - Async SQLite драйвер
- SQLite - Локальная БД

### AWS Integration
- [AWS Cognito](https://aws.amazon.com/cognito/) - User Pool + Identity Pool
- [AWS SigV4](https://docs.aws.amazon.com/general/latest/gr/signature-version-4.html) - Request signing
- [curl_cffi](https://github.com/yifeikong/curl_cffi) - CloudFront WAF bypass (Chrome impersonation)

### Monitoring & Observability
- [Prometheus](https://prometheus.io/) - Метрики и мониторинг
- [Grafana](https://grafana.com/) - Визуализация и дашборды
- [prometheus-client](https://github.com/prometheus/client_python) - Python metrics exporter

### Infrastructure
- [AWS Lightsail Container Service](https://aws.amazon.com/lightsail/) - Production hosting
- [Terraform](https://www.terraform.io/) - Infrastructure as Code
- [GitHub Actions](https://github.com/features/actions) - CI/CD
- [Docker](https://www.docker.com/) - Контейнеризация
- [supervisord](http://supervisord.org/) - Process manager (production)

## 📄 Лицензия

Private project

## 👥 Авторы

- Оригинальный проект: [@Ps1nu5](https://github.com/Ps1nu5)
- Fork и улучшения: [@DASHULYA1337](https://github.com/DASHULYA1337)
