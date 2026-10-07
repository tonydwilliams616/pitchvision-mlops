output "training_repository_url" {
  description = "Push/pull URL for the training image."
  value       = aws_ecr_repository.training.repository_url
}

output "training_repository_arn" {
  description = "ARN of the training image repository."
  value       = aws_ecr_repository.training.arn
}

output "inference_repository_url" {
  description = "Push/pull URL for the inference image."
  value       = aws_ecr_repository.inference.repository_url
}
