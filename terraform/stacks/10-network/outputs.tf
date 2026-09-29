output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "VPC CIDR block."
  value       = module.vpc.vpc_cidr_block
}

output "azs" {
  description = "Availability zones in use."
  value       = local.azs
}

output "private_subnet_ids" {
  description = "Private subnet IDs (EKS nodes and pods)."
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs (load balancers, NAT)."
  value       = module.vpc.public_subnets
}

output "nat_public_ips" {
  description = "Public IP(s) of the NAT gateway."
  value       = module.vpc.nat_public_ips
}

output "cluster_name" {
  description = "Cluster name used in discovery tags - consumed by 20-eks."
  value       = var.cluster_name
}
