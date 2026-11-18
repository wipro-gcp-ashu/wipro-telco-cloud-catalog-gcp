output "vnf_dataplane_ip" {
  value       = google_compute_instance.vnf_appliance.network_interface[1].network_ip
  description = "Dataplane internal IP address of the VNF appliance"
}

output "vnf_oam_ip" {
  value       = google_compute_instance.vnf_appliance.network_interface[0].network_ip
  description = "OAM management internal IP address of the VNF appliance"
}

