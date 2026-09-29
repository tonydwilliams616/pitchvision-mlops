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

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones to spread subnets across."
  type        = number
  default     = 3

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "EKS needs at least 2 AZs; this layout supports up to 3."
  }
}

variable "cluster_name" {
  description = "EKS cluster name - used in Karpenter subnet discovery tags. Must match the 20-eks stack."
  type        = string
  default     = "pitchvision-eks"
}
