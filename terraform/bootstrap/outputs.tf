output "state_bucket_name" {
  description = "S3 bucket holding Terraform state for all stacks."
  value       = aws_s3_bucket.tfstate.id
}

output "github_plan_role_arn" {
  description = "Role for terraform plan on pull requests - store as a GitHub Actions variable."
  value       = aws_iam_role.github_plan.arn
}

output "github_apply_role_arn" {
  description = "Role for terraform apply from the production environment - store as a GitHub Actions variable."
  value       = aws_iam_role.github_apply.arn
}

output "backend_config_example" {
  description = "Backend block to use in each stack (change the key per stack)."
  value       = <<-EOT
    backend "s3" {
      bucket       = "${aws_s3_bucket.tfstate.id}"
      key          = "<stack-name>/terraform.tfstate"
      region       = "${var.aws_region}"
      encrypt      = true
      use_lockfile = true
    }
  EOT
}
