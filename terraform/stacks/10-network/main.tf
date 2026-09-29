# -----------------------------------------------------------------------------
# Ephemeral network: destroyed after each working session by the
# Terraform Destroy workflow to avoid NAT gateway costs.
# -----------------------------------------------------------------------------

# Pick AZs by zone ID, not name - names map to different physical zones per
# account. use1-az3 does not support EKS control planes, so it's excluded.
data "aws_availability_zones" "available" {
  state            = "available"
  exclude_zone_ids = ["use1-az3"]

  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  # /19 private subnets (8,190 IPs each) - EKS gives every pod a VPC IP.
  # 10.0.0.0/19, 10.0.32.0/19, 10.0.64.0/19
  private_subnets = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 3, i)]

  # /24 public subnets for load balancers and the NAT gateway.
  # 10.0.96.0/24, 10.0.97.0/24, 10.0.98.0/24
  public_subnets = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 8, 96 + i)]
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0"

  name = "${var.project_name}-vpc"
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = local.private_subnets
  public_subnets  = local.public_subnets

  # One NAT gateway for the whole VPC (not one per AZ) - cost over resilience.
  enable_nat_gateway     = true
  single_nat_gateway     = true
  one_nat_gateway_per_az = false

  enable_dns_hostnames = true
  enable_dns_support   = true

  # Lets the AWS Load Balancer Controller place internet-facing LBs here
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  # Internal LBs + Karpenter node placement
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
    "karpenter.sh/discovery"          = var.cluster_name
  }
}

# Free gateway endpoint: keeps S3 traffic (including ECR image layers,
# which are served from S3) off the NAT gateway and its data charges.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(module.vpc.private_route_table_ids, module.vpc.public_route_table_ids)

  tags = {
    Name = "${var.project_name}-s3-endpoint"
  }
}
