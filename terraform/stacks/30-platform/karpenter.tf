# -----------------------------------------------------------------------------
# Karpenter - AWS side: controller IAM role (via Pod Identity), node IAM role +
# access entry, and an SQS queue fed by EventBridge so Karpenter gets advance
# warning of spot interruptions and can drain nodes gracefully.
# -----------------------------------------------------------------------------
module "karpenter" {
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "~> 21.0"

  cluster_name = local.cluster_name
  namespace    = "kube-system"

  create_pod_identity_association = true

  # Fixed name so the EC2NodeClass manifests in gitops/ can reference it
  node_iam_role_use_name_prefix = false
  node_iam_role_name            = "${local.cluster_name}-karpenter-node"

  # Lets you shell into Karpenter nodes via SSM Session Manager (no SSH keys)
  node_iam_role_additional_policies = {
    AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }
}

# -----------------------------------------------------------------------------
# Karpenter - cluster side. CRDs are a separate release because Helm never
# upgrades CRDs bundled inside a chart; a dedicated CRD chart can be upgraded.
# -----------------------------------------------------------------------------
resource "helm_release" "karpenter_crd" {
  name       = "karpenter-crd"
  namespace  = "kube-system"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter-crd"
  version    = var.karpenter_version
}

resource "helm_release" "karpenter" {
  name       = "karpenter"
  namespace  = "kube-system"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = var.karpenter_version
  skip_crds  = true
  wait       = true

  values = [yamlencode({
    settings = {
      clusterName       = local.cluster_name
      clusterEndpoint   = local.cluster_endpoint
      interruptionQueue = module.karpenter.queue_name
    }

    serviceAccount = {
      name = module.karpenter.service_account
    }

    # Run on the managed system nodes - never on nodes Karpenter itself manages
    nodeSelector = {
      "pitchvision.io/pool" = "system"
    }

    # Don't depend on in-cluster DNS (CoreDNS) to start
    dnsPolicy = "Default"

    controller = {
      resources = {
        requests = { cpu = "250m", memory = "512Mi" }
        limits   = { memory = "512Mi" }
      }
    }
  })]

  depends_on = [
    helm_release.karpenter_crd,
    module.karpenter,
  ]
}
