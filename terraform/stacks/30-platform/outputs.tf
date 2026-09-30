output "karpenter_node_role_name" {
  description = "IAM role for Karpenter-launched nodes - referenced by EC2NodeClass manifests."
  value       = module.karpenter.node_iam_role_name
}

output "karpenter_interruption_queue" {
  description = "SQS queue receiving spot interruption and instance state events."
  value       = module.karpenter.queue_name
}
