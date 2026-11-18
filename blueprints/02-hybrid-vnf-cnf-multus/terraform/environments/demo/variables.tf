variable "project_id" {
  type        = string
  default     = "gcp-oda-canvas-poc"
  description = "Target GCP Project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "GCP Region"
}

variable "zone" {
  type        = string
  default     = "us-central1-a"
  description = "GCP Zone for VM deployments"
}

variable "admin_cidr" {
  type        = string
  default     = "0.0.0.0/0"
  description = "Allowed CIDR for OAM management SSH access"
}
