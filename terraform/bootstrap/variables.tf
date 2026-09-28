variable "project_name" {
  description = "Prefix used for naming resources."
  type        = string
  default     = "pitchvision"
}

variable "aws_region" {
  description = "AWS region for the state bucket and all stacks."
  type        = string
  default     = "us-east-1"
}

variable "github_owner" {
  description = "GitHub user or organisation that owns the repo."
  type        = string
  default     = "tonydwilliams616"
}

variable "github_repo" {
  description = "GitHub repository name."
  type        = string
  default     = "pitchvision-mlops"
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false if one already exists in this account."
  type        = bool
  default     = true
}

variable "github_owner_id" {
  description = "Immutable numeric ID of the GitHub owner, included in the OIDC sub claim."
  type        = string
  default     = "219661695"
}

variable "github_repo_id" {
  description = "Immutable numeric ID of the GitHub repo, included in the OIDC sub claim."
  type        = string
  default     = "1391304432"
}
