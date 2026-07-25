# Databricks Workspace Configuration
terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token
}

provider "aws" {
  region = var.aws_region
}

# Databricks Cluster Configuration
resource "databricks_cluster" "weather_cluster" {
  cluster_name = "weather-processing-cluster"
  spark_version = "13.3.x-scala2.12"
  node_type_id = "i3.xlarge"
  autotermination_minutes = 30
  autoscale {
    min_workers = 1
    max_workers = 4
  }
  
  spark_conf = {
    "spark.databricks.delta.preview.enabled" = "true"
    "spark.sql.extensions" = "io.delta.sql.DeltaSparkSessionExtension"
    "spark.sql.catalog.spark_catalog" = "org.apache.spark.sql.delta.catalog.DeltaCatalog"
  }
  
  custom_tags = {
    "Environment" = var.environment
    "Project" = "weather-platform"
    "CostCenter" = "data-engineering"
  }
}

# Databricks Notebooks
resource "databricks_notebook" "ingest_weather" {
  path     = "/Users/${var.databricks_user}/weather/01_ingest_weather_data"
  language = "PYTHON"
  content_base64 = base64encode(file("../../databricks/notebooks/01_ingest_weather_data.py"))
}

resource "databricks_notebook" "bronze_to_silver" {
  path     = "/Users/${var.databricks_user}/weather/02_bronze_to_silver"
  language = "PYTHON"
  content_base64 = base64encode(file("../../databricks/notebooks/02_bronze_to_silver.py"))
}

resource "databricks_notebook" "silver_to_gold" {
  path     = "/Users/${var.databricks_user}/weather/03_silver_to_gold"
  language = "PYTHON"
  content_base64 = base64encode(file("../../databricks/notebooks/03_silver_to_gold.py"))
}

# Databricks Job - Ingestion
resource "databricks_job" "ingestion_job" {
  name = "weather_ingestion_job"
  
  schedule {
    quartz_cron_expression = "0 0 * * * ?"  # Hourly
    timezone_id = "UTC"
  }
  
  task {
    task_key = "ingest_weather"
    
    existing_cluster_id = databricks_cluster.weather_cluster.id
    
    notebook_task {
      notebook_path = databricks_notebook.ingest_weather.path
      source = "WORKSPACE"
    }
  }
  
  email_notifications {
    on_failure = var.alert_emails
  }
}

# Databricks Job - Bronze to Silver
resource "databricks_job" "bronze_silver_job" {
  name = "bronze_to_silver_job"
  
  schedule {
    quartz_cron_expression = "30 0 * * * ?"  # 30 minutes after ingestion
    timezone_id = "UTC"
  }
  
  task {
    task_key = "bronze_to_silver"
    
    existing_cluster_id = databricks_cluster.weather_cluster.id
    
    notebook_task {
      notebook_path = databricks_notebook.bronze_to_silver.path
      source = "WORKSPACE"
    }
  }
  
  email_notifications {
    on_failure = var.alert_emails
  }
}

# Databricks Job - Silver to Gold
resource "databricks_job" "silver_gold_job" {
  name = "silver_to_gold_job"
  
  schedule {
    quartz_cron_expression = "0 1 * * * ?"  # Hourly, after bronze->silver
    timezone_id = "UTC"
  }
  
  task {
    task_key = "silver_to_gold"
    
    existing_cluster_id = databricks_cluster.weather_cluster.id
    
    notebook_task {
      notebook_path = databricks_notebook.silver_to_gold.path
      source = "WORKSPACE"
    }
  }
  
  email_notifications {
    on_failure = var.alert_emails
  }
}