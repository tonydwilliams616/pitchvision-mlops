# -----------------------------------------------------------------------------
# EPHEMERAL NAT gateway - the only network component that costs money
# (~$0.045/hour + data + public IPv4). Destroyed every session by the Terraform
# Destroy workflow; the VPC itself (10-network) stays up permanently.
# -----------------------------------------------------------------------------
data "terraform_remote_state" "network" {
  backend = "s3"

  config = {
    bucket = "pitchvision-tfstate-352438994554"
    key    = "10-network/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  public_subnet_id        = data.terraform_remote_state.network.outputs.public_subnet_ids[0]
  private_route_table_ids = data.terraform_remote_state.network.outputs.private_route_table_ids
}

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-nat"
  }
}

# One NAT gateway in the first public subnet - cost over resilience
resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = local.public_subnet_id

  tags = {
    Name = "${var.project_name}-nat"
  }
}

# Default route for the private subnets: internet-bound traffic goes via the NAT.
# Removing this stack removes the route, leaving private subnets with no internet.
resource "aws_route" "private_default" {
  count = length(local.private_route_table_ids)

  route_table_id         = local.private_route_table_ids[count.index]
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this.id
}
