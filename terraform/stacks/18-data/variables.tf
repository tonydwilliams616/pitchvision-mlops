variable "project_name" {
  description = "Prefix used for naming resources."
  type        = string
  default     = "pitchvision"
}

variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL version. Must support Serverless v2 scale-to-zero (16.3+ or 17.x)."
  type        = string
  default     = "17.11"
}

variable "db_max_acu" {
  description = "Maximum Aurora capacity units (1 ACU ~ 2 GB memory)."
  type        = number
  default     = 2
}

variable "db_auto_pause_seconds" {
  description = "Idle seconds before the database pauses to zero capacity."
  type        = number
  default     = 300
}
