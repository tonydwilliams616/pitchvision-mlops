variable "project_name" {
  description = "Prefix used for naming resources and the Project tag value."
  type        = string
  default     = "pitchvision"
}

variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "alert_email" {
  description = "Email for budget and anomaly alerts. Supplied via TF_VAR_alert_email (GitHub secret ALERT_EMAIL in CI)."
  type        = string
  sensitive   = true
}

variable "monthly_budget_limit" {
  description = "Account-wide monthly budget in USD."
  type        = number
  default     = 50
}

variable "project_budget_limit" {
  description = "Monthly budget in USD for resources tagged Project=pitchvision."
  type        = number
  default     = 40
}

variable "activate_cost_allocation_tag" {
  description = "Activate the Project tag for cost allocation. Enable once the tag appears in Billing (up to 24h after first tagged resource)."
  type        = bool
  default     = false
}

variable "enable_anomaly_detection" {
  description = "Create the Cost Anomaly Detection monitor. Set false if the account already has a SERVICE monitor."
  type        = bool
  default     = true
}
