variable "environment" {
  description = "Deployment environment identifier."
  type        = string
}

variable "table_name" {
  description = "DynamoDB single-table name."
  type        = string
}

variable "bucket_name" {
  description = "S3 media bucket name (must be globally unique)."
  type        = string
}

variable "allowed_origins" {
  description = "Browser origins allowed for direct uploads (CORS)."
  type        = list(string)
  default     = ["http://localhost:3000"]
}
