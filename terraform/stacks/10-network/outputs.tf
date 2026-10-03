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

output "private_route_table_ids" {
  description = "Private route table IDs - 15-nat adds the default route via the NAT gateway here."
  value       = module.vpc.private_route_table_ids
}

output "cluster_name" {
  description = "Cluster name used in discovery tags - consumed by 20-eks."
  value       = var.cluster_name
}
