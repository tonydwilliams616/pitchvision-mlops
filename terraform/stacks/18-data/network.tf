# -----------------------------------------------------------------------------
# PERSISTENT data layer for MLflow. Never destroyed by the Terraform Destroy
# workflow - it holds experiment history, the model registry and model files.
# Lives in the permanent 10-network VPC.
# -----------------------------------------------------------------------------
data "aws_caller_identity" "current" {}

data "terraform_remote_state" "network" {
  backend = "s3"

  config = {
    bucket = "pitchvision-tfstate-352438994554"
    key    = "10-network/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  vpc_id             = data.terraform_remote_state.network.outputs.vpc_id
  vpc_cidr_block     = data.terraform_remote_state.network.outputs.vpc_cidr_block
  private_subnet_ids = data.terraform_remote_state.network.outputs.private_subnet_ids
}
