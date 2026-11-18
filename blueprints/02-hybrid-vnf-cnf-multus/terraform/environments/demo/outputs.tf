output "vnf_dataplane_ip" {
  value       = module.vnf.vnf_dataplane_ip
  description = "Internal IP of the VNF Appliance on the Data Plane VPC"
}

output "vnf_oam_ip" {
  value       = module.vnf.vnf_oam_ip
  description = "Internal IP of the VNF Appliance on the OAM Management VPC"
}

output "gke_cluster_name" {
  value       = module.cnf.cluster_name
  description = "GKE CNF Cluster Name"
}

