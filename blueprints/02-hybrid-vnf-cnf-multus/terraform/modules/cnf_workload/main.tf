resource "google_container_cluster" "gke_cnf_cluster" {
  name     = var.cluster_name
  location = var.region

  network    = var.oam_network_id
  subnetwork = var.oam_subnetwork_id

  remove_default_node_pool = true
  initial_node_count       = 1

  ip_allocation_policy {
    cluster_secondary_range_name  = "gke-pods-oam"
    services_secondary_range_name = "gke-services-oam"
  }

  network_policy {
    enabled = true
  }

  addons_config {
    network_policy_config {
      disabled = false
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

resource "google_container_node_pool" "cnf_nodes" {
  name       = "cnf-worker-pool"
  location   = var.region
  cluster    = google_container_cluster.gke_cnf_cluster.name

  autoscaling {
    total_min_node_count = 1
    total_max_node_count = 3
  }

  node_config {
    machine_type = "n2-standard-4"
    image_type   = "COS_CONTAINERD"

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    labels = {
      workload-type = "telco-cnf"
    }

    tags = ["telco-cnf-node", "dataplane"]
  }
}
