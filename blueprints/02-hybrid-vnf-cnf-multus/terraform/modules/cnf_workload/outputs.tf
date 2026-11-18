output "cluster_name" {
  value       = google_container_cluster.gke_cnf_cluster.name
  description = "Name of the GKE CNF cluster"
}

output "cluster_endpoint" {
  value       = google_container_cluster.gke_cnf_cluster.endpoint
  description = "Cluster endpoint"
}
