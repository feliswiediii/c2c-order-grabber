# Monitoring Setup for C2C Order Grabber Bot

Этот директория содержит конфигурацию для мониторинга бота через Prometheus и Grafana.

## 📊 Компоненты

- **Prometheus** - система сбора и хранения метрик
- **Grafana** - визуализация метрик и дашборды
- **Bot Metrics** - встроенный экспорт метрик на порту 9090

## 🚀 Быстрый старт

### Запуск с Docker Compose

```bash
# Из корневой директории проекта
docker-compose up -d

# Проверить статус
docker-compose ps

# Посмотреть логи
docker-compose logs -f bot
docker-compose logs -f prometheus
docker-compose logs -f grafana
```

### Доступ к сервисам

- **Bot Health Check:** http://localhost:8080/health
- **Bot Metrics (Prometheus format):** http://localhost:9090/metrics
- **Prometheus UI:** http://localhost:9091
- **Grafana UI:** http://localhost:3000

### Grafana Login

- **Username:** `admin`
- **Password:** `admin` (измените при первом входе)

## 📈 Доступные метрики

### Counters (монотонно растущие)

```promql
# Заказы
orders_seen_total{chat_id}           # Обнаружено заказов
orders_taken_total{chat_id}          # Успешно взято
orders_failed_total{chat_id,reason}  # Не взято (race_condition, auth_error, insufficient_balance, etc.)

# API запросы
api_requests_total{endpoint,method,status}  # Все API запросы (2xx/4xx/5xx/error)

# Poll циклы
poll_cycles_total{chat_id,result}    # Успешные/failed poll'ы

# Rate limiting
rate_limit_hits_total{chat_id}       # HTTP 429 ответы

# Авторизация
auth_refresh_total{chat_id,result}   # Refresh токенов (success/failure)
```

### Gauges (текущие значения)

```promql
active_sessions                              # Активных пользователей
queue_depth{chat_id}                         # Глубина очереди заказов
current_poll_interval_seconds{chat_id}       # Текущий интервал polling
```

### Histograms (распределение значений)

```promql
# Латентность polling
poll_duration_seconds{chat_id}               # p50, p95, p99

# Латентность взятия заказа
order_grab_duration_seconds{chat_id,result}  # p50, p95, p99 (success/failure)

# Время от обнаружения до взятия
time_to_grab_seconds{chat_id}                # p50, p95, p99

# Латентность API запросов
api_request_duration_seconds{endpoint,method} # p50, p95, p99
```

## 🔍 Примеры PromQL запросов

### Success Rate (последние 5 минут)

```promql
sum(rate(orders_taken_total[5m]))
/
(sum(rate(orders_taken_total[5m])) + sum(rate(orders_failed_total[5m])))
* 100
```

### Orders Seen per Minute

```promql
rate(orders_seen_total[1m]) * 60
```

### p99 Poll Latency

```promql
histogram_quantile(0.99,
  sum(rate(poll_duration_seconds_bucket[1m])) by (le, chat_id)
)
```

### API Error Rate

```promql
sum(rate(api_requests_total{status!="2xx"}[5m]))
/
sum(rate(api_requests_total[5m]))
```

### Average Time to Grab

```promql
histogram_quantile(0.50,
  sum(rate(time_to_grab_seconds_bucket[1m])) by (le, chat_id)
)
```

## 📊 Grafana Dashboard

Dashboard автоматически загружается при запуске Grafana и включает:

1. **Active Sessions** - количество активных пользователей
2. **Orders Seen Rate** - частота обнаружения новых заказов
3. **Success Rate Gauge** - процент успешно взятых заказов
4. **Poll Latency (p50/p95/p99)** - распределение латентности polling
5. **Order Outcomes Pie Chart** - взято vs failed (с причинами)
6. **Time to Grab** - время от обнаружения до взятия
7. **Adaptive Poll Interval** - текущий интервал с адаптацией
8. **Queue Depth** - глубина очереди обработки
9. **Rate Limit Hits** - частота HTTP 429 ошибок
10. **API Requests Breakdown** - все API запросы по endpoint'ам и статусам

### Редактирование Dashboard

1. Откройте http://localhost:3000
2. Войдите (admin/admin)
3. Перейдите в Dashboards → C2C Order Grabber Bot
4. Кликните на название панели → Edit
5. Сохраните изменения

Изменения в UI сохраняются в `monitoring/grafana/dashboards/c2c-bot-dashboard.json`.

## 🔧 Конфигурация

### Prometheus (`prometheus.yml`)

```yaml
scrape_configs:
  - job_name: 'c2c-bot'
    static_configs:
      - targets: ['bot:9090']
    scrape_interval: 5s  # Частота сбора метрик
```

**Настройки:**
- `scrape_interval: 5s` - собирать метрики каждые 5 секунд
- `retention: 30d` - хранить данные 30 дней

### Grafana Datasource

Автоматически настраивается через `provisioning/datasources/prometheus.yml`:

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
```

## 🐛 Troubleshooting

### Метрики не отображаются

1. Проверьте, что бот запущен и здоров:
   ```bash
   curl http://localhost:8080/health
   ```

2. Проверьте, что метрики экспортируются:
   ```bash
   curl http://localhost:9090/metrics
   ```

3. Проверьте targets в Prometheus:
   - Откройте http://localhost:9091/targets
   - `c2c-bot` должен быть UP

### Grafana не показывает данные

1. Проверьте datasource:
   - Grafana → Configuration → Data Sources → Prometheus
   - Нажмите "Test" - должно быть зелёное "Data source is working"

2. Проверьте временной диапазон:
   - В правом верхнем углу dashboard
   - Установите "Last 15 minutes"

### Prometheus не scrape'ит метрики

1. Проверьте сетевое соединение:
   ```bash
   docker-compose exec prometheus wget -O- http://bot:9090/metrics
   ```

2. Проверьте конфигурацию:
   ```bash
   docker-compose exec prometheus promtool check config /etc/prometheus/prometheus.yml
   ```

3. Перезапустите Prometheus:
   ```bash
   docker-compose restart prometheus
   ```

## 📦 Структура файлов

```
monitoring/
├── README.md                        # Эта документация
├── prometheus.yml                   # Конфигурация Prometheus
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── prometheus.yml       # Автоматическая настройка datasource
    │   └── dashboards/
    │       └── default.yml          # Провайдер dashboard'ов
    └── dashboards/
        └── c2c-bot-dashboard.json   # Главный dashboard
```

## 🔐 Безопасность

### Production рекомендации:

1. **Измените пароли:**
   ```yaml
   # docker-compose.yml
   grafana:
     environment:
       - GF_SECURITY_ADMIN_PASSWORD=your_strong_password_here
   ```

2. **Включите аутентификацию в Prometheus:**
   ```yaml
   # prometheus.yml
   basic_auth:
     username: admin
     password_file: /etc/prometheus/password
   ```

3. **Используйте reverse proxy (nginx):**
   ```nginx
   location /grafana/ {
       proxy_pass http://localhost:3000/;
       proxy_set_header Authorization $http_authorization;
   }
   ```

4. **Ограничьте доступ к портам:**
   ```yaml
   # docker-compose.yml
   ports:
     - "127.0.0.1:9091:9090"  # Только localhost
     - "127.0.0.1:3000:3000"  # Только localhost
   ```

## 📚 Дополнительные ресурсы

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Tutorial](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)

## 🎯 Следующие шаги

1. Добавить Alertmanager для уведомлений
2. Создать алерты для critical метрик (p99 latency > 1s, success rate < 80%)
3. Настроить Telegram-бот для алертов
4. Добавить метрики по использованию ресурсов (CPU, memory)
5. Создать long-term storage (Thanos/VictoriaMetrics)
