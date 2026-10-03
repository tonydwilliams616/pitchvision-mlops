output "artifacts_bucket_name" {
  description = "S3 bucket for MLflow artifacts."
  value       = aws_s3_bucket.artifacts.id
}

output "artifacts_bucket_arn" {
  description = "ARN of the MLflow artifacts bucket - used for the MLflow Pod Identity policy."
  value       = aws_s3_bucket.artifacts.arn
}

output "db_endpoint" {
  description = "Aurora writer endpoint."
  value       = aws_rds_cluster.mlflow.endpoint
}

output "db_port" {
  description = "Aurora port."
  value       = aws_rds_cluster.mlflow.port
}

output "db_name" {
  description = "Database name for MLflow."
  value       = aws_rds_cluster.mlflow.database_name
}

output "db_master_secret_arn" {
  description = "Secrets Manager secret holding the RDS-managed master credentials."
  value       = aws_rds_cluster.mlflow.master_user_secret[0].secret_arn
}

output "db_security_group_id" {
  description = "Security group attached to the database."
  value       = aws_security_group.db.id
}
