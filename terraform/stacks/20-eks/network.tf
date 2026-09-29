# Read VPC and subnet IDs from the 10-network stack's state.
# The network must be up before this stack can plan or apply.
data "terraform_remote_state" "network" {
  backend = "s3"

  config = {
    bucket = "pitchvision-tfstate-352438994554"
    key    = "10-network/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  cluster_name       = data.terraform_remote_state.network.outputs.cluster_name
  vpc_id             = data.terraform_remote_state.network.outputs.vpc_id
  private_subnet_ids = data.terraform_remote_state.network.outputs.private_subnet_ids
}
