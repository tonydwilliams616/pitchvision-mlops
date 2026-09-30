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

variable "karpenter_version" {
  description = "Karpenter chart version. Kubernetes 1.36 requires Karpenter 1.13.x (see karpenter.sh compatibility matrix)."
  type        = string
  default     = "1.14.1"
}
