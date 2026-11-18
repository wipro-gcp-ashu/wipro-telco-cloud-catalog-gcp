resource "google_compute_network" "oam_vpc" {
  name                    = "telco-oam-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "oam_subnet" {
  name                     = "telco-oam-subnet"
  ip_cidr_range            = var.oam_subnet_cidr # 10.10.0.0/24
  region                   = var.region
  network                  = google_compute_network.oam_vpc.id
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "gke-pods-oam"
    ip_cidr_range = "10.100.0.0/16"
  }

  secondary_ip_range {
    range_name    = "gke-services-oam"
    ip_cidr_range = "10.101.0.0/20"
  }
}

resource "google_compute_network" "dataplane_vpc" {
  name                    = "telco-dataplane-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "dataplane_subnet" {
  name          = "telco-dataplane-subnet"
  ip_cidr_range = var.dataplane_subnet_cidr # 10.20.0.0/24
  region        = var.region
  network       = google_compute_network.dataplane_vpc.id
}

# Firewall rule: OAM Management (SSH and Inter-Workload Service Traffic)
resource "google_compute_firewall" "oam_allow_internal_ssh" {
  name    = "oam-allow-ssh-mgmt"
  network = google_compute_network.oam_vpc.name

  allow {
    protocol = "all"
  }

  source_ranges = [var.admin_cidr, var.oam_subnet_cidr, "10.100.0.0/16"]
}

# Firewall rule: Data Plane (unrestricted internal traffic across 10.20.0.0/24 and peered OAM/GKE ranges)
resource "google_compute_firewall" "dataplane_allow_all" {
  name    = "dataplane-allow-internal"
  network = google_compute_network.dataplane_vpc.name

  allow {
    protocol = "all"
  }

  source_ranges = [var.dataplane_subnet_cidr, var.oam_subnet_cidr, "10.100.0.0/16"]
}

# VPC Peering between OAM VPC and Data Plane VPC for inter-plane service chaining
resource "google_compute_network_peering" "oam_to_dataplane" {
  name         = "peer-oam-to-dataplane"
  network      = google_compute_network.oam_vpc.self_link
  peer_network = google_compute_network.dataplane_vpc.self_link
}

resource "google_compute_network_peering" "dataplane_to_oam" {
  name         = "peer-dataplane-to-oam"
  network      = google_compute_network.dataplane_vpc.self_link
  peer_network = google_compute_network.oam_vpc.self_link
}

# Cloud NAT for outbound internet on OAM (required for packages and updates)
resource "google_compute_router" "oam_router" {
  name    = "telco-oam-router"
  region  = var.region
  network = google_compute_network.oam_vpc.id
}

resource "google_compute_router_nat" "oam_nat" {
  name                               = "telco-oam-nat"
  router                             = google_compute_router.oam_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
