variable "zone" {
  type        = string
  description = "GCP Zone"
}

variable "machine_type" {
  type        = string
  description = "GCE Instance machine type"
}

variable "oam_network_id" {
  type        = string
  description = "OAM VPC Network ID"
}

variable "oam_subnetwork_id" {
  type        = string
  description = "OAM Subnetwork ID"
}

variable "dataplane_network_id" {
  type        = string
  description = "Dataplane VPC Network ID"
}

variable "dataplane_subnetwork_id" {
  type        = string
  description = "Dataplane Subnetwork ID"
}

variable "dataplane_subnet_cidr" {
  type        = string
  description = "Dataplane Subnet CIDR"
}
