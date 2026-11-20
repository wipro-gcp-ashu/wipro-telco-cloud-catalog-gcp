terraform {
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.25"
    }
  }
  backend "gcs" {
    bucket = "wipro-telco-cloud-catalog1-tfstate"
    prefix = "hybrid-orchestration/wipro-telco-cloud-catalog"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

module "network" {
  source                = "../../modules/telco_network"
  region                = var.region
  oam_subnet_cidr       = "10.10.0.0/24"
  dataplane_subnet_cidr = "10.20.0.0/24"
  admin_cidr            = var.admin_cidr
}

module "vnf" {
  source                  = "../../modules/vnf_workload"
  zone                    = var.zone
  oam_network_id          = module.network.oam_network_id
  oam_subnetwork_id       = module.network.oam_subnetwork_id
  dataplane_network_id    = module.network.dataplane_network_id
  dataplane_subnetwork_id = module.network.dataplane_subnetwork_id
  dataplane_subnet_cidr   = "10.20.0.0/24"
  machine_type            = "n2-standard-4"
}

module "cnf" {
  source               = "../../modules/cnf_workload"
  project_id           = var.project_id
  region               = var.region
  cluster_name         = "telco-cnf-gke-poc"
  oam_network_id       = module.network.oam_network_id
  oam_subnetwork_id    = module.network.oam_subnetwork_id
  dataplane_network_id = module.network.dataplane_network_id
}
