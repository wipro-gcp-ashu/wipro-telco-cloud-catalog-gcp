# Wipro Telco Cloud Solution Catalogue on Google Cloud (`wipro-telco-cloud-catalog-gcp`)

**Wipro Google Cloud (GCP) Practice — Telecom Cloud Studio**  
**Standards Alignment:** TM Forum Open Digital Architecture (`IG1228`), Shared Information & Data Model (`SID GB922`), 3GPP Rel-17 5G SBA & O-RAN WG6 Cloudification  
**Live Executive Demo Portal (Cloud Run):** https://tmf-consolidated-dashboard-481157998097.us-central1.run.app/

---

## 1. Executive Summary & Consolidation Architecture

This master repository unifies all three Wipro GCP Telecom engineering assets into **one standardized, catalog-driven Telco Cloud Factory** on Google Cloud:

1. **`blueprints/01-oda-canvas-multitenant/`** *(from `oda-canvas-poc`)* — Shared Private GKE Standard Cluster (`oda-canvas-mt-gke`), Dataplane V2 Cilium eBPF zero-trust multi-tenancy, Cloud Armor WAF, Workload Identity Federation, and TM Forum ODA Canvas (`v1beta2`).
2. **`blueprints/02-hybrid-vnf-cnf-multus/`** *(from `telco-hybrid-orchestration`)* — Dual-VPC telecom separation (`telco-oam-vpc` + `telco-dataplane-vpc`), Dual-NIC Compute Engine VNFs (`nic0` OAM + `nic1` Data-Plane), and Multus CNI multi-interface GKE CNFs.
3. **`blueprints/03-5g-upf-network-slice/`** *(from `tmf-federated-catalog-gcp-poc`)* — 3GPP 5G User Plane Function (`UPF`) network slice (`SGi/N6`, `N3 GTP-U UDP/2152`, `N4 PFCP UDP/8805`), Workload Identity IAM, Regional Secret Manager, and GKE CNF worker pools.

Instead of exposing raw hardware complexity directly to enterprise or operator buyers, specialized telecom hardware and Kubernetes requirements (**SR-IOV, DPDK, IOMMU/VT-d, IEEE 1588v2 PTP, SyncE, GNSS, Single-NUMA, HugePages, Static CPU Pinning, BIOS C/P-State Lock, Intel vRAN Boost / ACC100 FEC, SmartNIC/DPU GTP-U Offload, QAT Crypto, Multus CNI, 25–400GbE, NEBS Level 3, Short-Depth -48V DC**) are modeled as **reusable machine-readable JSON RFS Infrastructure Profiles (`TMF633`)** and **atomic `TMF634` Resource Specifications**.

---

## 2. The 6 Commercial Telco Cloud Offerings (`TMF620`) & 5 Reusable RFS Profiles (`TMF633`)

| # | `TMF620` Offering ID | Commercial Offering Name | `TMF633` CFS | Reusable `TMF633` RFS Profile(s) | Target Execution Blueprint |
| :- | :--- | :--- | :--- | :--- | :--- |
| **1** | `prod-offer-5g-upf-hp-001` | **High-Performance 5G UPF Cloud Infrastructure Slice** *(Worked Example)* | `cfs-001-5g-upf-connectivity` | **`TELCO-UPF`** | `blueprints/03-5g-upf-network-slice` |
| **2** | `prod-offer-5g-core-cp-002` | **5G Core Control Plane Cloud Platform (3GPP SBA)** *(AMF/SMF/NRF/UDM/PCF)* | `cfs-002-5g-core-control-plane` | **`TELCO-GENERAL-CNF`** | `blueprints/01-oda-canvas-multitenant` |
| **3** | `prod-offer-hybrid-vnf-cnf-003` | **Hybrid VNF + CNF Multi-Network Service Chain** | `cfs-003-hybrid-vnf-cnf-chain` | **`TELCO-HP-CNF`** | `blueprints/02-hybrid-vnf-cnf-multus` |
| **4** | `prod-offer-oda-mt-slice-004` | **Multi-Tenant TM Forum ODA Canvas Partner Slice** *(MVNO / B2B)* | `cfs-004-oda-multitenant-slice` | **`TELCO-GENERAL-CNF`** | `blueprints/01-oda-canvas-multitenant` |
| **5** | `prod-offer-vran-oran-du-005` | **5G vRAN / O-RAN Distributed Unit (O-DU) Edge Platform** | `cfs-005-vran-oran-radio` | **`TELCO-vRAN`** + **`TELCO-EDGE`** | `blueprints/01-oda-canvas-multitenant` *(GDC Bare Metal)* |
| **6** | `prod-offer-telco-far-edge-006` | **Telco Far-Edge & NEBS Level 3 MEC Platform** | `cfs-006-telco-mec-far-edge` | **`TELCO-EDGE`** + **`TELCO-HP-CNF`** | `blueprints/01-oda-canvas-multitenant` *(GDC Connected)* |

---

## 3. Flagship Worked Example: High-Performance `5G UPF` Decomposition

1. **Customer View (`TMF620` / `TMF622` Order — `orders/order-01-5g-upf-hp-tenant-delta.json`)**:
   - Customer selects **`High-Performance 5G UPF Cloud Infrastructure Slice`** with business SLAs only:
     - `throughput_tier = "10Gbps"`, `latency_tier = "Ultra-Low"`, `redundancy = "active-standby"`, `region = "us-central1"`.
2. **Backend Decomposition (`TMFC003` Orchestrator → `TELCO-UPF` RFS Recipe)**:
   - `RULE-TELCO-LATENCY-01` (`Ultra-Low`) → `numa_nodes = 2`, `cpu_manager_policy = "static"`, `topology_manager_policy = "single-numa-node"`, `hugepages_enabled = true (1Gi)`, `dpdk_enabled = true`, `dataplane_mode = "SR-IOV"`, `multus_enabled = true (N3, N4, N6/SGi)`.
   - `RULE-TELCO-THRU-10G` (`10Gbps`) → `cpu_count = 16`, `ram_gb = 64 GiB`, `smartnic_dpu_model = "Google-Titanium-IPU-Native"`.
   - `RULE-TELCO-HA-03` (`active-standby`) → `worker_instances = 2`.
3. **Zero-Touch Execution (`TMF652` → Terraform + GKE → `TMF638`/`TMF639` Active Inventory)**:
   - Generates `build/tmf641-service-order.json`, `build/tmf652-resource-order.json`, `generated.auto.tfvars.json`, and `build/k8s-telco-slice-manifest.yaml`, provisions the 3GPP VPC/Subnets/Firewall/IAM/GKE pods, and marks `TMF638` & `TMF639` **`active`**.

---

## 4. 16-Capability Telco Hardware & Kubernetes Mapping Matrix (`catalogs/telco-hw-capability-matrix.json`)

| ID | Telco Requirement | Workload Need | Google Cloud / GKE / GDC Approach | Capability Tier | `TMF634` Spec |
| :- | :--- | :--- | :--- | :--- | :--- |
| **CAP-01** | **SR-IOV & Direct Device Access** | Sub-2ms vSwitch bypass for 5G UPF | GDC Bare Metal SR-IOV plugin; GCP C3/C4 gVNIC Tier-1 (up to 200 Gbps) | Tier 3: Specialized HW / GDC Bare Metal | `res-spec-004` |
| **CAP-02** | **DPDK & Poll-Mode Drivers (PMD)** | Line-rate user-space packet processing | DPDK containers on GKE C3/C4 (`net_gvnic`) or Bare Metal (`vfio-pci`) | Tier 2: Telco-Optimized K8s | `res-spec-004` |
| **CAP-03** | **IOMMU / Intel VT-d / AMD-Vi** | Safe DMA isolation for user-space VFs | Host BIOS/kernel `intel_iommu=on iommu=pt` on GDC Bare Metal | Tier 3: Specialized HW / GDC Bare Metal | `res-spec-004` |
| **CAP-04** | **IEEE 1588v2 PTP Timestamping** | ±1.5 µs phase sync for O-RAN 7.2x | `linuxptp` (`ptp4l`/`phc2sys`) operator + PTP NICs on GDC Edge | Tier 3: Specialized HW / GDC Bare Metal | `res-spec-006` |
| **CAP-05** | **SyncE & GNSS / GPS Reference** | Stratum-1 frequency & timing lock | Rooftop GNSS/SyncE OEM timing card + Managed Prometheus telemetry | Tier 4: Physical OEM / Partner Edge | `res-spec-006` |
| **CAP-06** | **Single-NUMA Socket Affinity** | Zero cross-socket QPI/UPI latency | Kubelet Topology Manager (`single-numa-node`) on dedicated pools | Tier 2: Telco-Optimized K8s | `res-spec-002` |
| **CAP-07** | **HugePages (2 MB & 1 GB)** | Zero-copy DPDK packet ring buffers | GKE Linux node-system-config (`hugepages-1Gi` / `hugepages-2Mi`) | Tier 2: Telco-Optimized K8s | `res-spec-003` |
| **CAP-08** | **CPU Pinning & Guaranteed QoS** | Zero context-switch packet threads | Kubelet `static` CPU Manager + Guaranteed QoS pods + taints | Tier 2: Telco-Optimized K8s | `res-spec-002` |
| **CAP-09** | **Deterministic BIOS C/P-States** | Eliminate CPU sleep-wake latency spikes | Bare-metal OEM BIOS profile (C-states disabled, P-states locked) | Tier 3: Specialized HW / GDC Bare Metal | `res-spec-002` |
| **CAP-10** | **5G L1 FEC (`vRAN Boost` / `ACC100`)** | Sub-ms LDPC Forward Error Correction | Intel `sriov-fec` device plugin on Xeon EE / ACC100 edge servers | Tier 3: Specialized HW / GDC Bare Metal | `res-spec-007` |
| **CAP-11** | **SmartNIC / DPU GTP-U Offload** | Hardware GTP-U encap/decap & vSwitch | Google Titanium IPU in GCP Region; BlueField-3 / Intel IPU at Edge | Tier 3: Specialized HW / GDC Bare Metal | `res-spec-007` |
| **CAP-12** | **IPSec / MACsec / TLS (`Intel QAT`)** | Wire-speed N3/fronthaul crypto offload | Cloud Interconnect MACsec in Region; Intel QAT plugin on Bare Metal | Tier 3: Specialized HW / GDC Bare Metal | `res-spec-007` |
| **CAP-13** | **Multus CNI & Multi-Network Pods** | Separate OAM, Signaling, Sync & User planes | GKE Multi-Networking + Multus `NetworkAttachmentDefinitions` | Tier 2: Telco-Optimized K8s | `res-spec-005` |
| **CAP-14** | **High-Density 25 / 100 / 200 / 400 GbE** | High-bandwidth backhaul & SGi breakout | GCP C3/C4 Tier-1 Networking (200G) + Cloud Interconnect (100G/400G) | Tier 1: Native Managed GCP / GKE | `res-spec-001` |
| **CAP-15** | **NEBS Level 3 Compliance** | Central Office thermal, fire & Zone-4 seismic | GDC Connected on NEBS-3 OEM servers (Dell XR8000 / HPE DL110) | Tier 4: Physical OEM / Partner Edge | `res-spec-008` |
| **CAP-16** | **Short-Depth (300–450mm) & -48V DC** | Cramped cell-site racks & telecom DC battery | Fleet-managed OEM short-depth `-48V DC` edge server BOM | Tier 4: Physical OEM / Partner Edge | `res-spec-008` |

---

## 5. Repository Structure

```text
wipro-telco-cloud-catalog-gcp/
├── catalogs/
│   ├── telco-hw-capability-matrix.json      # 16 Telco HW & K8s Requirements across 4 GCP/Edge Tiers
│   ├── tmf620-product-catalog/              # 6 Commercial Offerings + 6 ProductSpecifications
│   ├── tmf633-cfs-catalog/                  # 6 Customer-Facing Service Specs + TMFC003 Policy Rules
│   ├── tmf633-rfs-profiles/                 # 5 Reusable RFS Profiles (TELCO-GENERAL-CNF..TELCO-EDGE)
│   └── tmf634-resource-catalog/             # 10 Atomic ResourceSpecs bound to Blueprints 01..03
├── orders/                                  # 4 Sample TMF622 ProductOrders (5G UPF, Hybrid, ODA, vRAN)
├── orchestrator/
│   ├── telco_catalog_orchestrator.py        # Python TMFC003 Validator, Decomposer & Inventory Sync
│   ├── telco_catalog_orchestrator.js        # Zero-dependency Node.js companion CLI (Windows/macOS/Linux)
│   └── k8s-tmf-federated-api-gateway.yaml   # Live GKE OpenAPI Gateway (TMF620/633/634/638/639 + Matrix)
├── blueprints/
│   ├── 01-oda-canvas-multitenant/           # Private GKE + Dataplane V2 + Cloud Armor + ODA Canvas
│   ├── 02-hybrid-vnf-cnf-multus/            # Dual-VPC + Dual-NIC GCE VNF + Multus GKE CNF Chain
│   └── 03-5g-upf-network-slice/             # 3GPP 5G UPF VPC (SGi/N3/N4) + GTP-U/PFCP + Workload ID
├── docs/
│   └── index.html                           # 5-Page Executive Demo Portal (served on Cloud Run)
├── scripts/
│   ├── bootstrap-gcp-project.sh             # 1-command setup for wipro-telco-cloud-catalog1 OR any new project
│   └── bootstrap-gcp-project.ps1            # PowerShell equivalent for Windows workstations
└── .github/workflows/                       # 5 Automated GitOps CI/CD Pipelines (01..04 + 99 Teardown)
```

---

## 6. Quickstart Commands

### Validate All 4 Catalog Layers & Decompose Orders Locally
```bash
# Using Python 3.11+ (Linux / Cloud Shell / GitHub Actions)
python3 orchestrator/telco_catalog_orchestrator.py --mode validate-catalogs
python3 orchestrator/telco_catalog_orchestrator.py --mode decompose --order-file orders/order-01-5g-upf-hp-tenant-delta.json

# Or using Node.js (Windows / macOS / Linux — zero dependencies)
node orchestrator/telco_catalog_orchestrator.js --mode validate-catalogs
node orchestrator/telco_catalog_orchestrator.js --mode decompose --order-file orders/order-01-5g-upf-hp-tenant-delta.json
```

### Authorize Consolidated GCP Project (`wipro-telco-cloud-catalog1`) or Bootstrap a New Project
```bash
bash scripts/bootstrap-gcp-project.sh wipro-telco-cloud-catalog1 wipro-gcp-ashu/wipro-telco-cloud-catalog-gcp us-central1 oda-canvas-mt-gke
```
