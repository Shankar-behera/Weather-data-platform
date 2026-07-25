variable "databricks_host" {
  description = "Databricks workspace URL"
  type        = string
  sensitive   = true
}

variable "databricks_token" {
  description = "Databricks API token"
  type        = string
  sensitive   = true
}

variable "databricks_user" {
  description = "Databricks workspace user"
  type        = string
  default     = "admin"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "alert_emails" {
  description = "Email addresses for alerts"
  type        = list(string)
  default     = ["admin@example.com"]
}