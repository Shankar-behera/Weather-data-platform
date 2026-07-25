output "cluster_id" {
  description = "Databricks cluster ID"
  value       = databricks_cluster.weather_cluster.id
}

output "ingestion_job_id" {
  description = "Ingestion job ID"
  value       = databricks_job.ingestion_job.id
}

output "notebook_paths" {
  description = "Paths to Databricks notebooks"
  value = {
    ingest      = databricks_notebook.ingest_weather.path
    bronze_to_silver = databricks_notebook.bronze_to_silver.path
    silver_to_gold   = databricks_notebook.silver_to_gold.path
  }
}