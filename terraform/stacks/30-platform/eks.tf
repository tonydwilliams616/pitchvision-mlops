# Read cluster details from the 20-eks stack. The cluster must be up.
data "terraform_remote_state" "eks" {
  backend = "s3"

  config = {
    bucket = "pitchvision-tfstate-352438994554"
    key    = "20-eks/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  cluster_name     = data.terraform_remote_state.eks.outputs.cluster_name
  cluster_endpoint = data.terraform_remote_state.eks.outputs.cluster_endpoint
  cluster_ca       = data.terraform_remote_state.eks.outputs.cluster_certificate_authority_data
}
