# Production Deployment Guide

Этот гайд описывает деплой бота с **встроенными Prometheus + Grafana** в одном контейнере.

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────┐
│ AWS Lightsail Container (Dockerfile.production)     │
│                                                     │
│  ┌──────────┐  ┌────────────┐  ┌─────────┐         │
│  │   Bot    │→ │ Prometheus │→ │ Grafana │         │
│  │ port:9090│  │ port:9091  │  │port:3000│         │
│  └──────────┘  └────────────┘  └─────────┘         │
│       ↑              ↑               ↑              │
│       │              │               │              │
└───────┼──────────────┼───────────────┼──────────────┘
        │              │               │
     :8080          :9091           :3000 (HTTPS)
   (healthcheck)  (prometheus)    (grafana UI)
```

## 📦 Что включено

Один Docker-контейнер (`Dockerfile.production`) запускает:

1. **Bot** - Python приложение
   - Health check: `http://bot:8080/health`
   - Metrics endpoint: `http://bot:9090/metrics`

2. **Prometheus** - сбор и хранение метрик
   - UI: `http://bot:9091`
   - Scrape interval: 5s
   - Retention: 7 дней (экономия места)

3. **Grafana** - визуализация
   - UI: `https://your-lightsail-url.amazonaws.com/` (public endpoint)
   - Login: `admin` / `admin`
   - Auto-configured datasource + dashboard

**Управление:** `supervisord` запускает все 3 сервиса и автоматически перезапускает при падении.

## 💰 Стоимость

### Рекомендуемые размеры Lightsail Container:

| Size | vCPU | RAM | Цена/мес | Рекомендация |
|------|------|-----|----------|--------------|
| **micro** | 0.25 | 512MB | $7 | ❌ Слишком мало (будет OOM) |
| **small** | 0.5 | 1GB | $10 | ✅ **Минимум для продакшена** |
| **medium** | 1.0 | 2GB | $20 | ✅ Комфортно (если много пользователей) |
| **large** | 2.0 | 4GB | $40 | ⚠️ Избыточно для этого бота |

**Footprint all-in-one контейнера:**
- Bot: ~100MB RAM
- Prometheus (7d retention): ~50-80MB RAM
- Grafana: ~100-150MB RAM
- **Итого: ~250-330MB RAM**

**Recommendation:** Lightsail **small** (1GB RAM, $10/мес) - оставляет ~700MB свободно для буферов и спайков.

## 🚀 Деплой

### Автоматический (GitHub Actions)

1. **Убедитесь что GitHub Secrets настроены:**
   ```
   AWS_ACCESS_KEY_ID
   AWS_SECRET_ACCESS_KEY
   TELEGRAM_BOT_TOKEN
   ADMIN_CHAT_ID
   INVITE_CODE (optional)
   DOCKERHUB_USERNAME
   DOCKERHUB_TOKEN
   HTTP_PROXY (optional)
   HTTPS_PROXY (optional)
   ```

2. **Push в main branch:**
   ```bash
   git push origin main
   ```

3. **GitHub Actions автоматически:**
   - Соберёт `Dockerfile.production`
   - Push в Docker Hub
   - Задеплоит в AWS Lightsail
   - Expose Grafana на public endpoint (HTTPS)

4. **Получите URL:**
   ```bash
   aws lightsail get-container-services \
     --service-name c2c-order-grabber \
     --region eu-north-1 \
     --query 'containerServices[0].url' \
     --output text
   ```

   Результат: `https://c2c-order-grabber.xxxxx.eu-north-1.cs.amazonlightsail.com`

### Ручной деплой

```bash
# 1. Build production image
docker build -f Dockerfile.production -t c2c-bot-prod .

# 2. Test locally
docker run -p 3000:3000 -p 8080:8080 -p 9090:9090 -p 9091:9091 \
  --env-file .env \
  c2c-bot-prod

# 3. Open in browser
open http://localhost:3000  # Grafana
open http://localhost:9091  # Prometheus
open http://localhost:8080/health  # Bot health

# 4. Push to Docker Hub
docker tag c2c-bot-prod your-username/c2c-order-grabber:latest
docker push your-username/c2c-order-grabber:latest

# 5. Deploy to Lightsail (через Terraform или AWS CLI)
```

## 🔍 Мониторинг в Production

### Доступ к Grafana

1. Откройте: `https://your-lightsail-url.amazonaws.com/`
2. Login: `admin` / `admin`
3. ⚠️ **ВАЖНО:** Смените пароль при первом входе!

### Dashboard включает:

- **Active Sessions** - количество активных пользователей
- **Orders Seen Rate** - частота новых заказов
- **Success Rate** - % успешно взятых заказов
- **Poll Latency (p50/p95/p99)** - распределение задержки
- **Time to Grab** - время от обнаружения до взятия
- **Queue Depth** - глубина очереди
- **Rate Limits** - частота HTTP 429
- **API Requests** - все запросы с breakdown

### Prometheus Queries (примеры)

Откройте Prometheus UI: `http://your-ip:9091`

**Success rate за последние 5 минут:**
```promql
sum(rate(orders_taken_total[5m]))
/
(sum(rate(orders_taken_total[5m])) + sum(rate(orders_failed_total[5m])))
* 100
```

**p99 latency:**
```promql
histogram_quantile(0.99,
  sum(rate(poll_duration_seconds_bucket[1m])) by (le, chat_id)
)
```

## 📊 Проверка здоровья

### Health Checks

**Bot health:**
```bash
curl https://your-lightsail-url.amazonaws.com:8080/health
```

Ответ (healthy):
```
OK: 2 active sessions, last activity 3s ago
```

**Grafana health:**
```bash
curl https://your-lightsail-url.amazonaws.com/api/health
```

Ответ:
```json
{"database": "ok"}
```

### Logs

**Через AWS CLI:**
```bash
# Bot logs
aws lightsail get-container-log \
  --service-name c2c-order-grabber \
  --container-name c2c-bot \
  --region eu-north-1

# Supervisor logs (all services)
aws lightsail get-container-log \
  --service-name c2c-order-grabber \
  --container-name c2c-bot \
  --region eu-north-1 \
  | grep "supervisor"
```

**Внутри контейнера (если подключитесь):**
```bash
# Supervisor status
supervisorctl status

# Logs
tail -f /var/log/supervisor/bot.out.log
tail -f /var/log/supervisor/prometheus.out.log
tail -f /var/log/supervisor/grafana.out.log
```

## 🔧 Конфигурация

### Изменить Grafana пароль

**Вариант 1: Через UI**
1. Login в Grafana
2. Settings → Change Password

**Вариант 2: Через environment variable**

Обновите GitHub Secret `GF_ADMIN_PASSWORD`:
```bash
gh secret set GF_ADMIN_PASSWORD --body "your-new-password"
```

Затем redeploy.

### Увеличить retention Prometheus

Отредактируйте `Dockerfile.production` (строка с `--storage.tsdb.retention.time`):

```dockerfile
# Было: 7d
--storage.tsdb.retention.time=30d \
```

Rebuild и redeploy.

### Добавить custom dashboard

1. Создайте JSON в Grafana UI
2. Export dashboard JSON
3. Сохраните в `monitoring/grafana/dashboards/custom.json`
4. Commit и push - автоматически подхватится при следующем deploy

## 🐛 Troubleshooting

### Out of Memory (OOM)

**Symptoms:** Container перезапускается, в логах "Killed"

**Solution:** Увеличьте размер контейнера до **medium** (2GB):

```bash
# Через Terraform
# deploy/terraform/variables.tf
variable "container_power" {
  default = "medium"  # было "small"
}

terraform apply
```

### Grafana не показывает метрики

1. **Проверьте Prometheus targets:**
   - Откройте `http://your-ip:9091/targets`
   - `c2c-bot` должен быть **UP**

2. **Проверьте bot metrics endpoint:**
   ```bash
   curl http://your-ip:9090/metrics | grep orders_seen_total
   ```

3. **Проверьте Grafana datasource:**
   - Grafana → Configuration → Data Sources → Prometheus
   - URL должен быть: `http://localhost:9091`
   - Нажмите "Test" → должно быть зелёное "Data source is working"

### Медленный отклик Grafana

**Причина:** Prometheus retention слишком большой или много метрик.

**Solution 1:** Уменьшите retention (7d → 3d):
```dockerfile
--storage.tsdb.retention.time=3d \
```

**Solution 2:** Увеличьте размер контейнера до medium.

## 🔐 Безопасность в Production

### ⚠️ ОБЯЗАТЕЛЬНО СДЕЛАТЬ:

1. **Смените Grafana пароль!**
   ```bash
   # В Dockerfile.production найдите:
   admin_password = admin
   # Измените на сильный пароль
   ```

2. **Ограничьте доступ к Prometheus/Metrics**

   Prometheus (9091) и Metrics (9090) НЕ должны быть публичными. Только Grafana (3000).

   Lightsail автоматически expose только port из `public-endpoint` (3000 Grafana).

3. **Используйте HTTPS для Grafana**

   Lightsail автоматически предоставляет HTTPS для public endpoint.

4. **Enable Grafana authentication**

   Уже включено (`allow_sign_up = false`), но можно добавить OAuth/SAML.

## 📈 Scaling

### Горизонтальный scaling

Lightsail Container Service поддерживает **scale** parameter:

```bash
# deploy/terraform/variables.tf
variable "container_scale" {
  default = 2  # Было 1
}
```

⚠️ **НО:** С Prometheus это **не рекомендуется**, т.к. каждый инстанс будет собирать свои метрики.

**Для scaling:**
1. Используйте **vertical scaling** (увеличьте power: small → medium)
2. Или переходите на отдельный Prometheus cluster (вне контейнера)

### Вертикальный scaling

```bash
# Увеличение мощности
aws lightsail update-container-service \
  --service-name c2c-order-grabber \
  --power medium \
  --region eu-north-1
```

## 📚 Дополнительные ресурсы

- [AWS Lightsail Container Docs](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services.html)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Supervisor Documentation](http://supervisord.org/)

## 🆘 Support

При проблемах:
1. Проверьте logs через AWS CLI
2. Проверьте `/health` endpoint
3. Откройте issue в GitHub repo
