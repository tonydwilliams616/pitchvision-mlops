variable "argocd_chart_version" {
  description = "argo-cd Helm chart version (10.9.6 = Argo CD v3.5.3)."
  type        = string
  default     = "10.9.6"
}

variable "argocd_apps_chart_version" {
  description = "argocd-apps Helm chart version, used to create the root Application."
  type        = string
  default     = "2.0.6"
}

variable "gitops_repo_url" {
  description = "Git repository Argo CD syncs from (public, so no credentials needed)."
  type        = string
  default     = "https://github.com/tonydwilliams616/pitchvision-mlops.git"
}
