# -----------------------------------------------------------------------------
# Ephemeral EKS cluster: destroyed with the network by the Terraform Destroy
# workflow. Karpenter (added in 30-platform) will launch GPU/workload nodes;
# the managed node group here only runs system components.
# -----------------------------------------------------------------------------
data "aws_caller_identity" "current" {}

locals {
  # CI plan role - read-only cluster access so Helm-based stacks can plan on PRs
  plan_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-github-plan"
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = local.cluster_name
  kubernetes_version = var.kubernetes_version

  vpc_id     = local.vpc_id
  subnet_ids = local.private_subnet_ids

  # Public endpoint so GitHub Actions runners and your laptop can reach the API
  # (still requires IAM auth). Private endpoint for in-VPC traffic.
  endpoint_public_access  = true
  endpoint_private_access = true

  # Access entries only - no aws-auth ConfigMap
  authentication_mode = "API"

  # Gives the identity that creates the cluster (the CI apply role) admin,
  # which later stacks need to install Helm charts.
  enable_cluster_creator_admin_permissions = true

  # Humans with cluster-admin (your IAM Identity Center / IAM role)
  access_entries = merge(
    # Humans with cluster-admin
    {
      for name, arn in var.admin_principal_arns : name => {
        principal_arn = arn
        policy_associations = {
          admin = {
            policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
            access_scope = { type = "cluster" }
          }
        }
      }
    },
    # CI plan role: read-only, but including Secrets, because Helm stores
    # release state as Secrets and must read it to plan.
    {
      ci-plan = {
        principal_arn = local.plan_role_arn
        policy_associations = {
          view = {
            policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSAdminViewPolicy"
            access_scope = { type = "cluster" }
          }
        }
      }
    }
  )

  # EKS Pod Identity instead of IRSA - the newer, simpler way to give pods AWS permissions
  enable_irsa = false

  addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent    = true
      before_compute = true
    }
    eks-pod-identity-agent = {
      most_recent    = true
      before_compute = true
    }
  }

  # EKS already envelope-encrypts Kubernetes API data with an AWS-owned key.
  # Skipping a customer-managed KMS key avoids a new key (and cost) every spin-up.
  create_kms_key    = false
  encryption_config = null

  # Control plane logging off: on an ephemeral cluster, EKS can recreate the log
  # group after Terraform deletes it, breaking the next apply. Revisit if needed.
  create_cloudwatch_log_group = false
  enabled_log_types           = []

  eks_managed_node_groups = {
    system = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.system_node_instance_types
      capacity_type  = "SPOT" # cheap; acceptable for a portfolio cluster

      min_size     = 2
      max_size     = 3
      desired_size = 2

      labels = {
        "pitchvision.io/pool" = "system"
      }
    }
  }

  # Karpenter will find the node security group by this tag
  node_security_group_tags = {
    "karpenter.sh/discovery" = local.cluster_name
  }
}
