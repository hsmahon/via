variable "region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment identifier (dev/staging/prod)."
  type        = string
  default     = "dev"
}

variable "table_name" {
  description = "DynamoDB single-table name."
  type        = string
  default     = "via"
}

variable "bucket_name" {
  description = "S3 bucket for video uploads and processing artifacts."
  type        = string
}

variable "allowed_origins" {
  description = "Browser origins allowed to upload directly to S3 (CORS)."
  type        = list(string)
  default     = ["http://localhost:3000"]
}
