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

variable "kubernetes_version" {
  description = "EKS Kubernetes version. Use one in STANDARD support - extended support costs 6x more."
  type        = string
  default     = "1.36"
}

variable "admin_principal_arns" {
  description = "IAM principal ARNs (roles or users) given cluster-admin, keyed by a short name."
  type        = map(string)
  default = {
    tony = "arn:aws:iam::352438994554:user/terraform-sagemaker"
  }
}

variable "system_node_instance_types" {
  description = "Instance types for the system node group. Several types improve spot availability."
  type        = list(string)
  default     = ["m5.large", "m5a.large", "m6i.large", "m6a.large", "m7i.large"]
}
