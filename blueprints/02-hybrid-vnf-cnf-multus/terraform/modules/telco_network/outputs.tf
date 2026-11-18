output "oam_network_id" {
  value       = google_compute_network.oam_vpc.id
  description = "ID of the OAM VPC Network"
}

output "oam_subnetwork_id" {
  value       = google_compute_subnetwork.oam_subnet.id
  description = "ID of the OAM Subnetwork"
}

output "dataplane_network_id" {
  value       = google_compute_network.dataplane_vpc.id
  description = "ID of the Data Plane VPC Network"
}

output "dataplane_subnetwork_id" {
  value       = google_compute_subnetwork.dataplane_subnet.id
  description = "ID of the Data Plane Subnetwork"
}
