# C2C Order Grabber Bot

Telegram bot for automated monitoring and grabbing orders on Cards2Cards platform with AWS Cognito authentication.

> Fork of original project [Ps1nu5/c2c-order-grabber](https://github.com/Ps1nu5/c2c-order-grabber) with performance improvements, monitoring, and automated AWS Lightsail deployment.

## Core Features

### Functionality
- Real-time order monitoring
- Configurable amount filters (min/max)
- Automated AWS Cognito authentication with MFA
- Proxy support for IP blocking bypass
- SQLite database for settings and logs
- CloudFront WAF bypass via curl_cffi
- Notifications for grabbed and missed orders

### Performance and Reliability
- **Latency optimization:**
  - HTTP connection reuse (Keep-Alive 30s)
  - DNS caching (10 minutes)
  - TCP_NODELAY for minimal delay
  - Connection pooling (up to 20 connections)

- **Adaptive polling:**
  - Base interval: 0.5 seconds (with jitter ±20%)
  - Automatic doubling on rate limit (429)
  - Gradual recovery (95% × interval)
  - 5 second cap for API protection

- **Reliability:**
  - Idempotency-Key to prevent duplicates on timeouts
  - Retry logic: 3 attempts with linear backoff (0.3s × attempt)
  - Docker HEALTHCHECK (every 30s)
  - Automatic restart on failure

### Monitoring (Prometheus + Grafana)
- **Comprehensive dashboard** with 10 panels:
  - Active Sessions, Orders Seen Rate, Success Rate
  - Poll Latency (p50/p95/p99), Order Outcomes
  - Time to Grab (detection to success), Queue Depth
  - Rate Limits, API Requests breakdown

- **Metrics:**
  - **Counters:** orders_seen/taken/failed, api_requests, poll_cycles, rate_limits
  - **Gauges:** active_sessions, queue_depth, current_poll_interval
  - **Histograms:** poll_duration, order_grab_duration, time_to_grab

- **Production-ready:**
  - All-in-one container (Bot + Prometheus + Grafana)
  - 7 day metrics retention
  - HTTPS access to Grafana from anywhere
  - ~250-300MB RAM (fits in Lightsail small $10/month)

## Requirements

- Python 3.10+
- Telegram Bot Token (get from [@BotFather](https://t.me/botfather))
- Cards2Cards credentials

## Local Installation

### 1. Clone repository

```bash
git clone https://github.com/DASHULYA1337/c2c-order-grabber.git
cd c2c-order-grabber
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_telegram_chat_id_here

# Optional: invite code for access control
INVITE_CODE=your_secret_invite_code

# AWS Cognito (can leave as is)
AWS_REGION=us-east-1
COGNITO_CLIENT_ID=6eio0hlq4tmr2o9d30ht9cvfn7
COGNITO_USER_POOL_ID=us-east-1_9szPtqd8w
COGNITO_IDENTITY_POOL_ID=us-east-1:db254d71-fe90-4631-bee5-d7ed0a489588
```

### 5. Run bot

```bash
python main.py
```

## Usage

1. Start bot with `/start` command in Telegram
2. Enter invite code (if configured)
3. Enter Cards2Cards credentials
4. Configure amount filters (optional)
5. Start monitoring

### Bot Commands

- `/start` - Start bot / authenticate
- `/stop` - Stop monitoring
- `/settings` - Configure filters
- `/status` - View statistics

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token | - |
| `ADMIN_CHAT_ID` | Yes | Admin chat ID | - |
| `INVITE_CODE` | No | Invite code | - |
| `AWS_REGION` | No | AWS region | `us-east-1` |
| `DATABASE_URL` | No | Database URL | `sqlite+aiosqlite:///./data/bot.db` |
| `LOG_FILE` | No | Log file path | `bot.log` |
| `POLL_INTERVAL_S` | No | Poll interval (seconds) | `0.5` |
| `DEBUG` | No | Debug mode | `false` |
| `HTTP_PROXY` | No | HTTP proxy | - |
| `HTTPS_PROXY` | No | HTTPS proxy | - |

### Proxy Configuration

To bypass IP blocks configure proxy:

```env
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080
# SOCKS5 proxies supported
```

## Docker (local development with monitoring)

### Run full stack (Bot + Prometheus + Grafana)

```bash
docker-compose up -d
```

**Service access:**
- Bot health check: http://localhost:8080/health
- Bot metrics: http://localhost:9090/metrics
- Prometheus UI: http://localhost:9091
- Grafana Dashboard: http://localhost:3000 (admin/admin)

### View logs

```bash
docker-compose logs -f bot
docker-compose logs -f prometheus
docker-compose logs -f grafana
```

### Stop

```bash
docker-compose down
```

## Production Deployment (AWS Lightsail)

Automated deployment with Terraform and GitHub Actions.

### What gets deployed

**All-in-one container** (`Dockerfile.production`):
- Bot (Python app) - ports 8080 (health), 9090 (metrics)
- Prometheus - port 9091 (scraping metrics, 7 day retention)
- Grafana - port 3000 (HTTPS public access)

Everything managed via **supervisord** - automatic restart on failure.

### Quick Start

#### 1. Configure GitHub Secrets

In Settings → Secrets and variables → Actions add:

```
AWS_ACCESS_KEY_ID          # AWS credentials
AWS_SECRET_ACCESS_KEY      # AWS credentials
TELEGRAM_BOT_TOKEN         # Bot token
ADMIN_CHAT_ID              # Admin chat ID
INVITE_CODE                # (optional)
DOCKERHUB_USERNAME         # Docker Hub username
DOCKERHUB_TOKEN            # Docker Hub token
HTTP_PROXY                 # (optional)
HTTPS_PROXY                # (optional)
```

#### 2. Deploy infrastructure

```bash
cd deploy/terraform
terraform init
terraform apply
```

#### 3. Automatic deployment

```bash
git push origin main
```

GitHub Actions automatically:
- Builds production image
- Pushes to Docker Hub
- Deploys to AWS Lightsail
- Exposes Grafana on HTTPS

#### 4. Get Grafana URL

```bash
aws lightsail get-container-services \
  --service-name c2c-order-grabber \
  --region eu-north-1 \
  --query 'containerServices[0].url' \
  --output text
```

Result: `https://c2c-order-grabber.xxxxx.eu-north-1.cs.amazonlightsail.com`

Open in browser, login: `admin` / `admin` - **Change password immediately!**

## Architecture

### Producer-Consumer Pattern

```
OrderMonitor (Producer)
    ↓ (detected new order)
asyncio.Queue
    ↓ (FIFO)
OrderProcessor (Consumer)
    ↓ (attempt to grab)
API: POST /orders/{slug}/take
    ↓
Callbacks (on_taken / on_failed)
```

### Key Patterns

- **Per-user session isolation** - each user has own credentials and monitoring
- **Adaptive polling with jitter** - protection from bot detection
- **Credential auto-refresh** - tokens refresh ~1 hour before expiration
- **WAF bypass** - CloudFront bypass via curl_cffi with Chrome impersonation
- **Callback-based notifications** - clean layer separation

### Project Structure

```
c2c-order-grabber/
├── main.py              # Entry point
├── app.py               # Main application class
├── config.py            # Configuration
├── cognito_auth.py      # AWS Cognito authentication
├── api_client.py        # Cards2Cards API client
├── aws_signer.py        # AWS Signature V4
├── user_session.py      # User session management
├── monitor.py           # Order monitoring
├── processor.py         # Order processing
├── metrics.py           # Prometheus metrics
### Runtime & Frameworks
- [Python 3.11](https://www.python.org/) - Runtime
- [aiogram 3.7+](https://github.com/aiogram/aiogram) - Telegram Bot Framework (async)
- [aiohttp 3.9+](https://github.com/aio-libs/aiohttp) - Async HTTP client

### Database & ORM
- [SQLAlchemy 2.0+](https://www.sqlalchemy.org/) - Async ORM
- [aiosqlite](https://github.com/omnilib/aiosqlite) - Async SQLite driver
- SQLite - Local database

### AWS Integration
- [AWS Cognito](https://aws.amazon.com/cognito/) - User Pool + Identity Pool
- [AWS SigV4](https://docs.aws.amazon.com/general/latest/gr/signature-version-4.html) - Request signing
- [curl_cffi](https://github.com/yifeikong/curl_cffi) - CloudFront WAF bypass (Chrome impersonation)

### Monitoring & Observability
- [Prometheus](https://prometheus.io/) - Metrics and monitoring
- [Grafana](https://grafana.com/) - Visualization and dashboards
- [prometheus-client](https://github.com/prometheus/client_python) - Python metrics exporter

### Infrastructure
- [AWS Lightsail Container Service](https://aws.amazon.com/lightsail/) - Production hosting
- [Terraform](https://www.terraform.io/) - Infrastructure as Code
- [GitHub Actions](https://github.com/features/actions) - CI/CD
- [Docker](https://www.docker.com/) - Containerization
- [supervisord](http://supervisord.org/) - Process manager (production)

## License

Private project

## Authors

- Original project: [@Ps1nu5](https://github.com/Ps1nu5)
- Fork and improvements: [@DASHULYA1337](https://github.com/DASHULYA1337)
```
c2c-order-grabber/
├── main.py              # Entry point
├── src/                 # Source code
│   ├── app.py           # Main application class
│   ├── config.py        # Configuration
│   ├── cognito_auth.py  # AWS Cognito authentication
│   ├── api_client.py    # Cards2Cards API client
│   ├── aws_signer.py    # AWS Signature V4
│   ├── user_session.py  # User session management
│   ├── monitor.py       # Order monitoring
│   ├── processor.py     # Order processing
│   ├── metrics.py       # Prometheus metrics
│   ├── bot/             # Telegram bot
│   │   ├── handlers/    # Command handlers
│   │   │   ├── auth.py      # Authentication
│   │   │   ├── control.py   # Control (start/stop)
│   │   │   ├── settings.py  # Filter settings
│   │   │   └── main_menu.py # Main menu
│   │   └── keyboards.py     # Keyboards
│   └── db/              # Database
│       ├── engine.py    # SQLAlchemy engine
│       ├── models.py    # Data models
│       └── repository.py # Repositories
├── deploy/              # Deployment
│   └── terraform/       # Infrastructure as Code
├── benchmark/           # RTT testing
│   ├── Dockerfile       # Benchmark container
│   ├── measure_rtt.py   # Latency measurement
│   └── deploy_benchmark.sh # Multi-region deployment
├── monitoring/          # Monitoring configuration
│   ├── prometheus.yml
│   └── grafana/
│       ├── provisioning/
│       └── dashboards/
├── Dockerfile           # Development image
├── Dockerfile.production # Production all-in-one
├── docker-compose.yml   # Local stack
└── requirements.txt     # Dependencies
```

## Security

- Never commit `.env` file to git
- Use strong invite codes
- Securely store private keys
- Regularly update dependencies
- Change default Grafana password (`admin`)

