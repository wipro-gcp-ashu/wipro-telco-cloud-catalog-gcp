resource "google_compute_instance" "vnf_appliance" {
  name         = "vnf-firewall-router"
  machine_type = var.machine_type
  zone         = var.zone

  can_ip_forward = true # Mandatory for VNF packet routing & translation

  # Interface nic0: OAM VPC
  network_interface {
    network    = var.oam_network_id
    subnetwork = var.oam_subnetwork_id
  }

  # Interface nic1: Data Plane VPC
  network_interface {
    network    = var.dataplane_network_id
    subnetwork = var.dataplane_subnetwork_id
  }

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 30
      type  = "pd-balanced"
    }
  }

  metadata_startup_script = <<-EOF
    #!/bin/bash
    set -e
    echo "==> Configuring VNF Networking..."
    sysctl -w net.ipv4.ip_forward=1
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

    # Secondary interface configuration for ens5 (nic1)
    ip link set dev ens5 up || true
    NIC1_IP=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/1/ip)
    NIC1_GW=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/1/gateway)

    # Route dataplane traffic table
    ip route add ${var.dataplane_subnet_cidr} dev ens5 src $NIC1_IP table 200 || true
    ip route add default via $NIC1_GW dev ens5 table 200 || true
    ip rule add from $NIC1_IP lookup 200 || true

    echo "VNF Network initialisation completed."
  EOF

  tags = ["telco-vnf", "dataplane"]
}
