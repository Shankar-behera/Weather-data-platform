# Setup Guide

## Overview

This guide walks through setting up the Weather Data Platform from a clean machine to a running pipeline: ingestion → Delta Lake → dbt/DuckDB → Streamlit dashboard.

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12+ | Used by the ingestion service, dbt, and Streamlit |
| OpenWeatherMap API key | Free tier is sufficient — [openweathermap.org/api](https://openweathermap.org/api) |
| Databricks account | Community Edition works for local/dev use |
| Docker + Docker Compose | Optional, but recommended for a one-command environment |
| Git | To clone the repository |

## 2. Clone the Repository

```bash
git clone  https://github.com/Shankar-behera/Weather-data-platform.git
cd weather-data-platform
```

## 3. Configure Environment Variables

Copy the template and fill in your own values:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key | Required |
| `OPENWEATHER_BASE_URL` | API base URL | `https://api.openweathermap.org/data/2.5` |
| `CITIES` | Comma-separated cities to monitor | `London,New York,Tokyo,Sydney,Berlin,Mumbai,Singapore,Dubai` |
| `DATABRICKS_HOST` | Databricks workspace URL | Required |
| `DATABRICKS_TOKEN` | Databricks personal access token | Required |
| `DATABRICKS_CATALOG` | Catalog name | `weather` |
| `DATABRICKS_SCHEMA` | Schema name | `bronze` |
| `BRONZE_TABLE` | Bronze table name | `weather_bronze` |
| `SILVER_TABLE` | Silver table name | `weather_silver` |
| `GOLD_TABLE` | Gold table name | `weather_gold` |
| `MAX_RETRIES` | API retry attempts | `3` |
| `RETRY_DELAY` | Retry delay in seconds | `5` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FORMAT` | Log format | `json` |

**Getting a Databricks token:** In your Databricks workspace, go to **Settings → Developer → Access tokens → Generate new token**, then copy it into `DATABRICKS_TOKEN`.

## 4. Install Dependencies

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt
```

## 5. Set Up Databricks

1. Confirm `DATABRICKS_HOST` and `DATABRICKS_TOKEN` are set in `.env`.
2. Create the catalog and schemas referenced by `DATABRICKS_CATALOG` / `DATABRICKS_SCHEMA` if they don't already exist.
3. Run the table creation notebooks (or equivalent client calls) to provision the Bronze, Silver, and Gold tables:
   - `databricks/notebooks/01_ingest_weather_data.py`
   - `databricks/notebooks/02_bronze_to_silver.py`
   - `databricks/notebooks/03_silver_to_gold.py`

   Or, from Python: `DatabricksClient().create_bronze_table()`, `.create_silver_table()`, `.create_gold_table()`.

## 6. Configure dbt

```bash
cd dbt_weather
```

Set up `profiles.yml` to point at your Databricks SQL warehouse (host, HTTP path, and token — the token can reference the same `DATABRICKS_TOKEN` env var). Then verify the connection:

```bash
dbt debug
```

## 7. Run the Pipeline Locally

```bash
# 1. Run the ingestion pipeline (fetches weather data → Bronze)
python -m ingestion.main

# 2. Run dbt transformations (Bronze → Silver → Gold, tests, docs)
cd dbt_weather
dbt build

# 3. Start the Streamlit dashboard
cd ..
streamlit run streamlit_app/app.py
```

The dashboard should open automatically at `http://localhost:8501`.

## 8. Run with Docker Instead (Recommended)

Once `.env` is configured, a single command brings up ingestion, dbt, and the dashboard together:

```bash
docker-compose -f docker/docker-compose.yml up -d
```

Check container status and logs:

```bash
docker-compose -f docker/docker-compose.yml ps
docker-compose -f docker/docker-compose.yml logs -f
```

## 9. Verify the Setup

- **Ingestion**: check `monitoring/logs/` or container logs for successful fetch entries per city.
- **Bronze/Silver/Gold**: query the tables in Databricks SQL editor, or run `DatabricksClient().execute_query(...)`.
- **dbt**: `dbt test` should pass; `dbt docs generate && dbt docs serve` to browse model docs.
- **Dashboard**: open `http://localhost:8501` and confirm the Overview page shows KPIs for your configured cities.

## 10. Automate with GitHub Actions

The repository ships three workflows under `.github/workflows/`:

| Workflow | Trigger | Purpose |
|---|---|---|
| `ingest.yml` | Hourly schedule | Runs the ingestion pipeline |
| `dbt.yml` | After ingestion | Runs dbt models and tests |
| `quality.yml` | Pull request + daily | Linting, unit tests, data quality checks |

To enable them, add the following as GitHub repository secrets (Settings → Secrets and variables → Actions):

- `OPENWEATHER_API_KEY`
- `DATABRICKS_HOST`
- `DATABRICKS_TOKEN`

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `WeatherAPIError` on ingestion | Invalid or missing `OPENWEATHER_API_KEY` | Check the key in `.env` and your OpenWeatherMap account status |
| `dbt debug` fails to connect | Wrong host/HTTP path/token in `profiles.yml` | Re-check the Databricks SQL warehouse connection details |
| Dashboard shows no data | Pipeline hasn't run yet, or Gold tables are empty | Run `python -m ingestion.main` then `dbt build` before starting Streamlit |
| Docker containers exit immediately | Missing or malformed `.env` | Confirm `.env` exists in the project root and has no missing required values |

## Next Steps

- Review [`architecture.md`](./architecture.md) for how data flows through the platform.
- Review [`api_reference.md`](./api_reference.md) for the full module and method reference.