terraform {
  backend "s3" {
    bucket       = "pitchvision-tfstate-352438994554"
    key          = "bootstrap/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}