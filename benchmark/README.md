# RTT Benchmark for C2C Order Grabber

Этот набор скриптов измеряет сетевую латентность (RTT) до `api.cards2cards.com` из разных AWS регионов, используя Lightsail Container Service.

## 📋 Что измеряется

- **DNS resolution time** — время DNS-резолвинга
- **TCP handshake** — время TCP-соединения (**= 1 RTT**)
- **TLS handshake** — время TLS-рукопожатия (TCP + TLS)
- **HTTP request** — полное время HTTP-запроса (DNS + TCP + TLS + HTTP)

## 🚀 Быстрый старт

### Предварительные требования

1. **AWS CLI** — установлен и настроен
   ```bash
   aws configure
   ```

2. **Docker** — установлен и запущен
   ```bash
   docker --version
   ```

3. **jq** — утилита для парсинга JSON (опционально, установится автоматически на macOS)
   ```bash
   brew install jq  # macOS
   ```

### Запуск benchmark

```bash
cd benchmark
chmod +x deploy_benchmark.sh
./deploy_benchmark.sh
```

Скрипт автоматически:
1. Соберёт Docker-образ с benchmark скриптом
2. Развернёт Lightsail Container Service в каждом регионе
3. Запустит benchmark в каждом контейнере
4. Соберёт результаты из логов
5. Удалит все созданные ресурсы
6. Покажет сравнительную таблицу

### Тестирование конкретных регионов

```bash
# Только US и EU регионы
./deploy_benchmark.sh us-east-1 eu-west-1 eu-north-1

# Только текущий регион и ближайший конкурент
./deploy_benchmark.sh eu-north-1 eu-central-1
```

## 📊 Пример вывода

```
================================================
BENCHMARK SUMMARY
================================================

📊 RTT Results by Region:

Region                RTT (ms)   TCP (ms)   TLS (ms)  HTTP (ms)
--------------------------------------------------------------------------------
us-east-1                4.2ms      4.3ms      9.1ms     15.7ms
us-west-2               78.5ms     79.1ms    156.2ms    203.4ms
eu-west-1               92.3ms     93.7ms    185.1ms    241.8ms
eu-central-1           105.7ms    106.2ms    209.3ms    267.5ms
eu-north-1             118.4ms    119.1ms    234.7ms    298.2ms
ap-southeast-1         245.6ms    246.3ms    487.9ms    612.3ms
ap-northeast-1         198.7ms    199.4ms    395.2ms    501.8ms

📁 Full results saved to: results/rtt_results_20260101_120000.json

🏆 Best region: us-east-1 (RTT: 4.2ms)
```

## 📁 Структура результатов

```
benchmark/
├── results/
│   ├── rtt_results_20260101_120000.json  # JSON с полными результатами
│   ├── logs_us-east-1_20260101_120000.txt
│   ├── logs_eu-west-1_20260101_120000.txt
│   └── ...
```

### Формат JSON результатов

```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "regions": {
    "us-east-1": {
      "url": "https://api.cards2cards.com",
      "ip_address": "13.35.123.45",
      "runs": 20,
      "tcp_handshake": {
        "min": 3.8,
        "median": 4.3,
        "mean": 4.5,
        "p95": 5.1,
        "p99": 5.6,
        "max": 6.2,
        "stdev": 0.7
      },
      "estimated_rtt_ms": 4.3
    }
  }
}
```

## 🧪 Локальное тестирование (без AWS)

Можно запустить benchmark локально:

```bash
# Локально (без Docker)
python3 measure_rtt.py

# С Docker
docker build -t rtt-benchmark .
docker run --rm rtt-benchmark
```

## 💰 Стоимость

- **Lightsail Container Service (nano tier):** $7/месяц минимум
- **Benchmark длится ~5 минут на регион**
- Скрипт автоматически удаляет сервисы после завершения
- **Итого:** Почти бесплатно (charged только за минуты работы)

⚠️ **Важно:** Скрипт автоматически удаляет созданные ресурсы, но на всякий случай проверьте:

```bash
# Проверить оставшиеся сервисы
for region in us-east-1 eu-west-1 eu-north-1; do
  echo "Region: $region"
  aws lightsail get-container-services --region $region
done

# Удалить вручную
aws lightsail delete-container-service \
  --region us-east-1 \
  --service-name rtt-benchmark-us-east-1
```

## 🔧 Кастомизация

### Изменить целевой URL

```python
# measure_rtt.py
TARGET_URL = "https://your-api.example.com"
```

### Изменить количество измерений

```python
# measure_rtt.py
NUM_RUNS = 50  # Вместо 20
```

### Добавить новые регионы

```bash
# deploy_benchmark.sh
AVAILABLE_REGIONS=(
    "us-east-1"
    "your-new-region"
)
```

## 📈 Интерпретация результатов

### RTT (Round-Trip Time)

- **< 10ms** — Отличная латентность (API в том же регионе/дата-центре)
- **10-50ms** — Хорошая латентность (тот же континент)
- **50-150ms** — Приемлемо (трансконтинентально в пределах одного полушария)
- **150-300ms** — Высокая латентность (между континентами)
- **> 300ms** — Очень высокая латентность (может быть проблема)

### Что выбрать?

1. **Минимальный RTT** — если приоритет скорость grabbing
2. **Баланс RTT + стоимость** — если важна экономия
3. **Географическая близость к пользователям** — если есть UI компонент

Для вашего бота (автоматический grabbing заказов) критичен **минимальный RTT**.

## 🐛 Troubleshooting

### Ошибка: "Service already exists"

Скрипт автоматически удалит старый сервис. Если нет — удалите вручную:

```bash
aws lightsail delete-container-service \
  --region REGION \
  --service-name rtt-benchmark-REGION
```

### Ошибка: "No logs available"

Увеличьте время ожидания в скрипте (строка с `sleep 30`).

### Ошибка: "Failed to push image"

Проверьте Docker daemon и права доступа AWS:

```bash
docker ps  # Должен работать
aws lightsail get-container-services --region us-east-1  # Должен работать
```

## 📚 Дополнительная информация

- [AWS Lightsail Container Services](https://lightsail.aws.amazon.com/ls/docs/en_us/articles/amazon-lightsail-container-services)
- [RTT vs Latency vs Throughput](https://www.cloudflare.com/learning/performance/glossary/what-is-latency/)
