variable "project_id" {
  type        = string
  description = "GCP Project ID"
}

variable "region" {
  type        = string
  description = "GCP Region"
}

variable "cluster_name" {
  type        = string
  description = "GKE CNF Cluster Name"
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
