variable "region" {
  type        = string
  description = "GCP Region"
}

variable "oam_subnet_cidr" {
  type        = string
  description = "CIDR range for OAM Subnet"
}

variable "dataplane_subnet_cidr" {
  type        = string
  description = "CIDR range for Data Plane Subnet"
}

variable "admin_cidr" {
  type        = string
  description = "Allowed CIDR range for admin SSH access"
}
