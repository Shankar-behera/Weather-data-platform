# API Reference Documentation

## Overview

This document provides comprehensive API reference for the Weather Data Platform components.

## Ingestion Module

### WeatherService

The main service for fetching weather data from OpenWeatherMap API.

#### `fetch_weather_data(city: str) -> Optional[WeatherPayload]`

Fetches weather data for a specific city.

**Parameters:**
- `city` (str): City name

**Returns:**
- `WeatherPayload`: Parsed weather data
- `None`: If fetch fails

**Example:**
```python
from ingestion.service import WeatherService

service = WeatherService()
data = service.fetch_weather_data("London")
if data:
    print(f"Temperature: {data.temperature}°C")
```

#### `fetch_all_cities() -> List[WeatherPayload]`

Fetches weather data for all configured cities.

**Returns:**
- `List[WeatherPayload]`: List of weather data

**Example:**
```python
all_cities = service.fetch_all_cities()
for city_data in all_cities:
    print(f"{city_data.city}: {city_data.temperature}°C")
```

#### `create_bronze_records(weather_data: List[WeatherPayload]) -> List[RawWeatherRecord]`

Creates bronze layer records from weather data.

**Parameters:**
- `weather_data`: List of `WeatherPayload` objects

**Returns:**
- `List[RawWeatherRecord]`: Bronze layer records

#### `create_silver_records(weather_data: List[WeatherPayload]) -> List[SilverWeatherRecord]`

Creates silver layer records from weather data.

**Parameters:**
- `weather_data`: List of `WeatherPayload` objects

**Returns:**
- `List[SilverWeatherRecord]`: Silver layer records

### DatabricksClient

Client for interacting with Databricks Delta Lake.

#### `get_connection() -> Connection`

Gets or creates a Databricks SQL connection.

**Returns:**
- `Connection`: Databricks connection

#### `execute_query(query: str, params: Optional[Dict] = None) -> List[Dict]`

Executes a SQL query on Databricks.

**Parameters:**
- `query` (str): SQL query
- `params` (Dict): Query parameters

**Returns:**
- `List[Dict]`: Query results

#### `create_bronze_table()`

Creates the bronze table if it doesn't exist.

#### `create_silver_table()`

Creates the silver table if it doesn't exist.

#### `create_gold_table()`

Creates the gold table if it doesn't exist.

#### `insert_bronze_records(records: List[RawWeatherRecord])`

Inserts records into the bronze table.

**Parameters:**
- `records`: List of `RawWeatherRecord` objects

#### `insert_silver_records(records: List[SilverWeatherRecord])`

Inserts records into the silver table.

**Parameters:**
- `records`: List of `SilverWeatherRecord` objects

#### `optimize_tables(table_name: str)`

Optimizes a Delta table with Z-order and compaction.

**Parameters:**
- `table_name` (str): Name of the table

#### `get_table_history(table_name: str, limit: int = 10) -> List[Dict]`

Gets table history for time travel queries.

**Parameters:**
- `table_name` (str): Name of the table
- `limit` (int): Number of versions to return

**Returns:**
- `List[Dict]`: Historical versions

#### `time_travel_query(table_name: str, timestamp: str) -> List[Dict]`

Queries a table at a specific point in time.

**Parameters:**
- `table_name` (str): Name of the table
- `timestamp` (str): Timestamp

**Returns:**
- `List[Dict]`: Query results

## DuckDB Analytics

### DuckDBAnalytics

Analytics layer using DuckDB.

#### `get_global_kpis() -> Dict`

Gets global KPIs across all cities.

**Returns:**
- `Dict`: Global KPIs

**Example:**
```python
from duckdb.analytics import get_analytics

analytics = get_analytics()
kpis = analytics.get_global_kpis()
print(f"Global average temperature: {kpis['global_avg_temp']}°C")
print(f"Hottest city: {kpis['hottest_city']}")
```

#### `get_city_summary(city: str) -> pd.DataFrame`

Gets weather summary for a specific city.

**Parameters:**
- `city` (str): City name

**Returns:**
- `pd.DataFrame`: City summary

**Example:**
```python
df = analytics.get_city_summary("London")
print(df.head())
```

#### `get_extreme_weather_events(days: int = 7) -> pd.DataFrame`

Gets recent extreme weather events.

**Parameters:**
- `days` (int): Number of days to look back

**Returns:**
- `pd.DataFrame`: Extreme events

#### `get_quality_metrics() -> pd.DataFrame`

Gets data quality metrics.

**Returns:**
- `pd.DataFrame`: Quality metrics

#### `get_forecast_data(city: str, days: int = 7) -> pd.DataFrame`

Gets historical and forecast data for a city.

**Parameters:**
- `city` (str): City name
- `days` (int): Number of days to include

**Returns:**
- `pd.DataFrame`: Time series data

## Data Models

### WeatherPayload

Weather data model.

| Field | Type | Description |
|-------|------|--------------|
| `city` | str | City name |
| `temperature` | float | Temperature in Celsius |
| `humidity` | int | Humidity percentage |
| `pressure` | int | Atmospheric pressure |
| `wind_speed` | float | Wind speed in km/h |
| `weather_main` | str | Main weather category |
| `weather_description` | str | Detailed weather description |
| `timestamp` | datetime | Observation time |

### RawWeatherRecord

Bronze layer record model.

| Field | Type | Description |
|-------|------|--------------|
| `ingestion_id` | str | Unique identifier |
| `ingestion_time` | datetime | Ingestion time |
| `source` | str | Data source |
| `source_city` | str | City name |
| `raw_payload` | dict | Raw JSON data |
| `api_response_time` | float | API response time |

### SilverWeatherRecord

Silver layer record model.

| Field | Type | Description |
|-------|------|--------------|
| `city` | str | City name |
| `temperature_celsius` | float | Temperature in Celsius |
| `humidity` | int | Humidity percentage |
| `pressure` | int | Atmospheric pressure |
| `wind_speed` | float | Wind speed |
| `weather_main` | str | Main weather category |
| `weather_description` | str | Weather description |
| `observation_time` | datetime | Observation time |
| `ingestion_id` | str | Ingestion ID |
| `processed_time` | datetime | Processing time |
| `is_valid` | bool | Validation status |
| `quality_checks_passed` | int | Number of quality checks passed |
| `quality_checks_total` | int | Total quality checks |

## Configuration

### WeatherConfig

Configuration management.

**Environment Variables:**

| Variable | Description | Default |
|----------|--------------|---------|
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key | Required |
| `OPENWEATHER_BASE_URL` | API base URL | `https://api.openweathermap.org/data/2.5` |
| `CITIES` | Cities to monitor | `London,New York,Tokyo,Sydney,Berlin,Mumbai,Singapore,Dubai` |
| `DATABRICKS_HOST` | Databricks workspace | Required |
| `DATABRICKS_TOKEN` | Databricks token | Required |
| `DATABRICKS_CATALOG` | Catalog name | `weather` |
| `DATABRICKS_SCHEMA` | Schema name | `bronze` |
| `BRONZE_TABLE` | Bronze table name | `weather_bronze` |
| `SILVER_TABLE` | Silver table name | `weather_silver` |
| `GOLD_TABLE` | Gold table name | `weather_gold` |
| `MAX_RETRIES` | Retry attempts | `3` |
| `RETRY_DELAY` | Retry delay (seconds) | `5` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FORMAT` | Log format | `json` |

## Error Handling

### Custom Exceptions

#### `WeatherAPIError`

Raised when OpenWeatherMap API returns an error.

**Attributes:**
- `status_code` (int): HTTP status code
- `message` (str): Error message

#### `ValidationError`

Raised when data validation fails.

**Attributes:**
- `errors` (List): List of validation errors

#### `DatabricksError`

Raised when Databricks operations fail.

**Attributes:**
- `query` (str): Failed query
- `error` (str): Error message

## Example Usage

### Complete Pipeline Example

```python
# Import modules
from ingestion.service import WeatherService
from ingestion.databricks_client import DatabricksClient
from duckdb.analytics import get_analytics

# Initialize services
weather_service = WeatherService()
databricks = DatabricksClient()
analytics = get_analytics()

# 1. Fetch weather data
weather_data = weather_service.fetch_all_cities()

# 2. Load to bronze
bronze_records = weather_service.create_bronze_records(weather_data)
databricks.insert_bronze_records(bronze_records)

# 3. Transform to silver
silver_records = weather_service.create_silver_records(weather_data)
databricks.insert_silver_records(silver_records)

# 4. Run analytics
kpis = analytics.get_global_kpis()
print(f"Global avg temperature: {kpis['global_avg_temp']}°C")

# 5. Check data quality
quality_df = analytics.get_quality_metrics()
print(f"Data quality: {quality_df}")
```

### Dashboard Integration

```python
# Streamlit integration
import streamlit as st
from duckdb.analytics import get_analytics

analytics = get_analytics()

# Get data
kpis = analytics.get_global_kpis()
df = analytics.get_city_summary("London")

# Display
st.metric("Global Temperature", f"{kpis['global_avg_temp']:.1f}°C")
st.dataframe(df)
```

## Rate Limiting

The API client includes automatic retry logic with exponential backoff.

**Configuration:**
- Max retries: 3
- Initial delay: 5 seconds
- Backoff multiplier: 2

## Monitoring

### Logging

Structured JSON logging is supported:

```json
{
    "time": "2024-01-01T12:00:00Z",
    "name": "ingestion.service",
    "level": "INFO",
    "message": "Successfully fetched weather for London",
    "metrics": {
        "city": "London",
        "status": "success",
        "duration_ms": 450.5,
        "rows_processed": 1
    }
}
```

### Metrics

Custom metrics available:

| Metric Name | Description | Unit |
|--------------|--------------|------|
| `ingestion.total_records_24h` | Records ingested in 24h | records |
| `ingestion.hours_since_last` | Hours since last ingestion | hours |
| `silver.avg_quality_score` | Average quality score | score |
| `delta.{table}.size_bytes` | Table size | bytes |
| `weather.global_avg_temp` | Global average temperature | celsius |
| `quality.valid_ratio` | Valid records ratio | percent |