# Account-level guardrails. This stack is never destroyed - it keeps watching
# spend even when the EKS stacks are torn down between sessions.
module "cost_guardrails" {
  source = "../../modules/cost-guardrails"

  project_name         = var.project_name
  alert_email          = var.alert_email
  monthly_budget_limit = var.monthly_budget_limit
  project_budget_limit = var.project_budget_limit

  project_tag_key              = "Project"
  project_tag_value            = var.project_name
  activate_cost_allocation_tag = var.activate_cost_allocation_tag

  enable_anomaly_detection = var.enable_anomaly_detection
  anomaly_threshold_usd    = 10
}
