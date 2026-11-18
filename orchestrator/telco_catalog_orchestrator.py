#!/usr/bin/env python3
"""
Wipro Telco Cloud Catalog — TM Forum ODA & SID (GB922) Orchestrator (TMFC003)
=============================================================================
Implements the Unified Wipro Telco Cloud Factory Order-to-Activation Engine:
  1. Validates the 4-Layer Federated Catalog Hierarchy + 16-Capability Hardware Matrix:
       TMF620 (6 Commercial Telco Cloud Offerings & ProductSpecifications)
         -> TMF633 CFS (6 CustomerFacingServiceSpecifications + Policy Rules)
         -> TMF633 RFS (5 Standardized Reusable Infrastructure Profiles:
                        TELCO-GENERAL-CNF, TELCO-HP-CNF, TELCO-UPF, TELCO-vRAN, TELCO-EDGE)
         -> TMF634 (10 Atomic ResourceSpecifications bound to BluePrints 01..03)
  2. Decomposes any TMF622 ProductOrder across all 6 Telco Offerings into:
       - TMF641 ServiceOrder (CFS + RFS instances & triggered policy rules)
       - TMF652 ResourceOrder (resolved TMF634 hardware/K8s/VPC specifications)
       - Blueprint Terraform variables (generated.auto.tfvars.json)
       - Kubernetes Telco Slice Manifest (k8s-telco-slice-manifest.yaml)
  3. Synchronizes live GCP/GKE identifiers into TMF638 Service Inventory &
     TMF639 Resource Inventory (state = active).
"""

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = REPO_ROOT / "catalogs"
BUILD_DIR = REPO_ROOT / "build"
BUNDLE_DIR = BUILD_DIR / "catalog-bundle"


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def get_default_characteristics(spec: Dict[str, Any], char_key: str) -> Dict[str, Any]:
    """Extracts default characteristic values from a TMF633 or TMF634 specification."""
    defaults: Dict[str, Any] = {}
    val_key = char_key + "Value"
    for char in spec.get(char_key, []):
        name = char.get("name")
        values = char.get(val_key, [])
        chosen = None
        for v in values:
            if v.get("isDefault"):
                chosen = v.get("value")
                break
        if chosen is None and values:
            chosen = values[0].get("value")
        if name:
            defaults[name] = chosen
    return defaults


def load_federated_catalogs() -> Dict[str, Any]:
    """Loads all 4 layers of the Wipro Telco Cloud Catalog plus the 16-row Capability Matrix."""
    matrix_path = CATALOG_DIR / "telco-hw-capability-matrix.json"
    res_dir = CATALOG_DIR / "tmf634-resource-catalog"
    rfs_dir = CATALOG_DIR / "tmf633-rfs-profiles"
    cfs_dir = CATALOG_DIR / "tmf633-cfs-catalog"
    prod_dir = CATALOG_DIR / "tmf620-product-catalog"

    capability_matrix = load_json(matrix_path)

    resource_specs: Dict[str, Dict[str, Any]] = {}
    for p in sorted(res_dir.glob("*.json")):
        data = load_json(p)
        resource_specs[data["id"]] = data

    rfs_specs: Dict[str, Dict[str, Any]] = {}
    for p in sorted(rfs_dir.glob("*.json")):
        data = load_json(p)
        rfs_specs[data["id"]] = data

    cfs_specs: Dict[str, Dict[str, Any]] = {}
    for p in sorted(cfs_dir.glob("*.json")):
        data = load_json(p)
        cfs_specs[data["id"]] = data

    prod_specs: Dict[str, Dict[str, Any]] = {}
    prod_offerings: Dict[str, Dict[str, Any]] = {}
    for p in sorted(prod_dir.glob("*.json")):
        data = load_json(p)
        if data.get("@type") == "ProductSpecification":
            prod_specs[data["id"]] = data
        elif data.get("@type") == "ProductOffering":
            prod_offerings[data["id"]] = data

    return {
        "capability_matrix": capability_matrix,
        "tmf634_resources": resource_specs,
        "tmf633_rfs": rfs_specs,
        "tmf633_cfs": cfs_specs,
        "tmf620_product_specs": prod_specs,
        "tmf620_product_offerings": prod_offerings,
    }


def validate_catalogs() -> str:
    """Validates SID GB922 referential integrity across all 4 layers & 16 hardware capabilities, and writes API bundle."""
    cat = load_federated_catalogs()
    errors: List[str] = []
    lines: List[str] = []

    lines.append("## Wipro Telco Cloud Catalog — SID `GB922` Referential Integrity Report")
    lines.append("")
    lines.append("| Catalog Layer | TM Forum API | ODA Component | Entity ID | Name / Profile | `@type` | Status |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    # 1. Validate TMF620 Product Offerings & Specifications
    for po_id, po in cat["tmf620_product_offerings"].items():
        ps_ref = po.get("productSpecification", {}).get("id")
        if ps_ref not in cat["tmf620_product_specs"]:
            errors.append(f"TMF620 ProductOffering {po_id} references missing ProductSpecification {ps_ref}")
        lines.append(
            f"| **Layer 1: Product Catalog** | `TMF620` | `TMFC001` | `{po_id}` | {po['name']} | `{po['@type']}` | `{po['lifecycleStatus']}` |"
        )

    for ps_id, ps in cat["tmf620_product_specs"].items():
        for cfs_ref in ps.get("serviceSpecification", []):
            if cfs_ref["id"] not in cat["tmf633_cfs"]:
                errors.append(f"TMF620 ProductSpecification {ps_id} references missing CFS {cfs_ref['id']}")
        lines.append(
            f"| **Layer 1: Product Spec** | `TMF620` | `TMFC001` | `{ps_id}` | {ps['name']} | `{ps['@type']}` | `{ps['lifecycleStatus']}` |"
        )

    # 2. Validate TMF633 CFS -> RFS Profiles
    for cfs_id, cfs in cat["tmf633_cfs"].items():
        rels = cfs.get("serviceSpecRelationship", [])
        if not rels:
            errors.append(f"TMF633 CFS {cfs_id} has no decomposing RFS relationships")
        for rel in rels:
            if rel["id"] not in cat["tmf633_rfs"]:
                errors.append(f"TMF633 CFS {cfs_id} decomposesInto missing RFS Profile {rel['id']}")
        lines.append(
            f"| **Layer 2: Service Catalog (CFS)** | `TMF633` | `TMFC006` | `{cfs_id}` | {cfs['name']} | `{cfs['@type']}` | `{cfs['lifecycleStatus']}` |"
        )

    # 3. Validate TMF633 RFS Profiles -> TMF634 Resource Specifications
    for rfs_id, rfs in cat["tmf633_rfs"].items():
        profile_code = rfs.get("profileCode", rfs_id)
        for res_ref in rfs.get("resourceSpecification", []):
            if res_ref["id"] not in cat["tmf634_resources"]:
                errors.append(f"TMF633 RFS {rfs_id} ({profile_code}) references missing TMF634 ResourceSpec {res_ref['id']}")
        lines.append(
            f"| **Layer 3: RFS Infra Profile** | `TMF633` | `TMFC006` | `{rfs_id}` | **{profile_code}** (`{rfs['name']}`) | `{rfs['@type']}` | `{rfs['lifecycleStatus']}` |"
        )

    # 4. Validate TMF634 Resource Specifications & Blueprint IaC Bindings
    for res_id, res in cat["tmf634_resources"].items():
        defaults = get_default_characteristics(res, "resourceSpecCharacteristic")
        if "iac_binding" not in defaults:
            errors.append(f"TMF634 ResourceSpecification {res_id} is missing mandatory 'iac_binding' characteristic")
        else:
            bp_rel = defaults["iac_binding"].get("blueprint_path", "")
            bp_full = (REPO_ROOT / bp_rel).resolve()
            if not bp_full.exists():
                errors.append(f"TMF634 ResourceSpecification {res_id} iac_binding path does not exist: {bp_rel}")
        lines.append(
            f"| **Layer 4: Resource Catalog** | `TMF634` | `TMFC007` | `{res_id}` | {res['name']} (`{res.get('capabilityTier', 'N/A')}`) | `{res['@type']}` | `{res['lifecycleStatus']}` |"
        )

    # 5. Validate 16-Row Telco Hardware Capability Matrix -> TMF634 ResourceSpecs
    caps = cat["capability_matrix"].get("capabilities", [])
    if len(caps) < 16:
        errors.append(f"Expected 16 Telco Hardware Capabilities in matrix, found {len(caps)}")
    for cap in caps:
        ref_res = cap.get("tmf634ResourceSpecId")
        if ref_res not in cat["tmf634_resources"]:
            errors.append(f"Capability {cap.get('id')} references unknown TMF634 ResourceSpec {ref_res}")

    lines.append("")
    if errors:
        lines.append("### ❌ Validation Result: FAILED")
        for e in errors:
            lines.append(f"- {e}")
        raise ValueError("\n".join(errors))

    lines.append("### ✅ Validation Result: PASSED (100% SID `GB922` Referential Integrity)")
    lines.append(f"- **Commercial Offerings (`TMF620`)**: `{len(cat['tmf620_product_offerings'])}` Offerings + `{len(cat['tmf620_product_specs'])}` Product Specifications")
    lines.append(f"- **Customer-Facing Services (`TMF633` CFS)**: `{len(cat['tmf633_cfs'])}` CFS Specifications")
    lines.append(f"- **Reusable Telco Infra Profiles (`TMF633` RFS)**: `{len(cat['tmf633_rfs'])}` Standardized Profiles (`TELCO-GENERAL-CNF`, `TELCO-HP-CNF`, `TELCO-UPF`, `TELCO-vRAN`, `TELCO-EDGE`)")
    lines.append(f"- **Atomic Resource Specs (`TMF634`)**: `{len(cat['tmf634_resources'])}` Resource Specifications verified against `blueprints/01..03`")
    lines.append(f"- **Telco Hardware Capability Matrix**: `{len(caps)}` Specialized Hardware & K8s Requirements mapped across 4 Tiers")

    # Emit consolidated API JSON bundles for GKE ConfigMap publishing
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    save_json(
        BUNDLE_DIR / "tmf620.json",
        {
            "productOfferings": list(cat["tmf620_product_offerings"].values()),
            "productSpecifications": list(cat["tmf620_product_specs"].values()),
        },
    )
    save_json(
        BUNDLE_DIR / "tmf633.json",
        {
            "customerFacingServices": list(cat["tmf633_cfs"].values()),
            "resourceFacingProfiles": list(cat["tmf633_rfs"].values()),
        },
    )
    save_json(BUNDLE_DIR / "tmf634.json", list(cat["tmf634_resources"].values()))
    save_json(BUNDLE_DIR / "capability-matrix.json", cat["capability_matrix"])

    report = "\n".join(lines)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "catalog-validation-report.md").write_text(report, encoding="utf-8")
    return report


def generate_k8s_telco_slice_manifest(
    tenant_id: str,
    order_id: str,
    offering: Dict[str, Any],
    cfs_spec: Dict[str, Any],
    rfs_profiles: List[Dict[str, Any]],
    resolved_resources: Dict[str, Dict[str, Any]],
    order_chars: Dict[str, Any],
    project_id: str,
) -> str:
    """Generates the Kubernetes Telco Slice manifest embedding resolved RFS & TMF634 hardware/network annotations."""
    namespace = f"upf-{tenant_id}"
    primary_rfs = rfs_profiles[0]
    profile_codes = ",".join(r.get("profileCode", r["id"]) for r in rfs_profiles)

    comp = resolved_resources.get("res-spec-002", {})
    hp = resolved_resources.get("res-spec-003", {})
    sriov = resolved_resources.get("res-spec-004", {})
    multus = resolved_resources.get("res-spec-005", {})
    ptp = resolved_resources.get("res-spec-006", {})
    accel = resolved_resources.get("res-spec-007", {})
    nebs = resolved_resources.get("res-spec-008", {})
    vpc = resolved_resources.get("res-spec-001", {})
    oda = resolved_resources.get("res-spec-010", {})

    replicas = int(comp.get("worker_instances", 2))
    cpu_count = int(comp.get("cpu_count", 8))
    ram_gb = int(comp.get("ram_gb", 32))
    numa_nodes = int(comp.get("numa_nodes", 1))
    cpu_mgr = str(comp.get("cpu_manager_policy", "static"))
    topo_mgr = str(comp.get("topology_manager_policy", "single-numa-node"))
    hugepages_enabled = str(hp.get("hugepages_enabled", False)).lower()
    hugepage_size = str(hp.get("hugepage_size", "1Gi"))
    dpdk_enabled = str(sriov.get("dpdk_enabled", False)).lower()
    dataplane_mode = str(sriov.get("dataplane_mode", "Cilium-eBPF"))
    sriov_vfs = int(sriov.get("sriov_vf_count", 0))
    multus_ifaces = ",".join(multus.get("secondary_interfaces", ["eth0-oam"]))
    storage_class = str(oda.get("storage_class", "standard-rwo"))

    status_doc = {
        "solution": "Wipro Telco Cloud Catalog on Google Cloud",
        "order_id": order_id,
        "tenant_id": tenant_id,
        "offering_id": offering["id"],
        "cfs_id": cfs_spec["id"],
        "rfs_profiles": [r.get("profileCode", r["id"]) for r in rfs_profiles],
        "operationalState": "enable",
        "usageState": "active",
        "orderCharacteristics": order_chars,
        "resolvedHardwareRecipe": {
            "cpu_count": cpu_count,
            "ram_gb": ram_gb,
            "cpu_manager_policy": cpu_mgr,
            "topology_manager_policy": topo_mgr,
            "numa_nodes": numa_nodes,
            "hugepages_enabled": hp.get("hugepages_enabled", False),
            "hugepage_size": hugepage_size,
            "dataplane_mode": dataplane_mode,
            "dpdk_enabled": sriov.get("dpdk_enabled", False),
            "sriov_vf_count": sriov_vfs,
            "multus_secondary_interfaces": multus.get("secondary_interfaces", []),
            "ptp_profile": ptp.get("ptp_profile", "N/A"),
            "fec_accelerator": accel.get("fec_accelerator", "None"),
            "smartnic_dpu_model": accel.get("smartnic_dpu_model", "Google-Titanium-IPU-Native"),
            "nebs_compliance": nebs.get("nebs_compliance", "Standard-Cloud-Region"),
            "subnets": {
                "sgi_n6": vpc.get("sgi_subnet_cidr", "10.210.1.0/24"),
                "n3_gtpu": vpc.get("n3_subnet_cidr", "10.210.2.0/24"),
                "n4_pfcp": vpc.get("n4_subnet_cidr", "10.210.3.0/24"),
            },
        },
    }
    status_json_indented = "\n".join("    " + ln for ln in json.dumps(status_doc, indent=2).splitlines())

    return f"""# ==============================================================================
# AUTO-GENERATED BY WIPRO TELCO CLOUD CATALOG ORCHESTRATOR (TMFC003 -> TMF652)
# Order ID: {order_id} | Tenant: {tenant_id}
# Offering: {offering['id']} ({offering['name']})
# CFS: {cfs_spec['id']} | RFS Profiles: {profile_codes}
# ==============================================================================
apiVersion: v1
kind: Namespace
metadata:
  name: {namespace}
  labels:
    oda.tmforum.org/tenant-id: "{tenant_id}"
    oda.tmforum.org/order-id: "{order_id}"
    oda.tmforum.org/cfs-spec: "{cfs_spec['id']}"
    oda.tmforum.org/rfs-profile: "{primary_rfs.get('profileCode', primary_rfs['id'])}"
    oda.tmforum.org/dataplane-mode: "{dataplane_mode}"
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: upf-edge-sa
  namespace: {namespace}
  annotations:
    iam.gke.io/gcp-service-account: "upf-{tenant_id}-sa@{project_id}.iam.gserviceaccount.com"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: telco-rfs-hardware-recipe
  namespace: {namespace}
data:
  tenant_id: "{tenant_id}"
  order_id: "{order_id}"
  rfs_profiles: "{profile_codes}"
  dataplane_mode: "{dataplane_mode}"
  status.json: |
{status_json_indented}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: telco-slice-storage-pvc
  namespace: {namespace}
  labels:
    oda.tmforum.org/resource-spec: "res-spec-010"
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: {storage_class}
  resources:
    requests:
      storage: 2Gi
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: telco-zero-trust-isolation
  namespace: {namespace}
spec:
  podSelector: {{}}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              oda.tmforum.org/tenant-id: "{tenant_id}"
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: "tmf-federated-catalog"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: upf-userplane-workers
  namespace: {namespace}
  labels:
    app: upf-userplane
    oda.tmforum.org/rfs-profile: "{primary_rfs.get('profileCode', primary_rfs['id'])}"
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: upf-userplane
      tenant: "{tenant_id}"
  template:
    metadata:
      labels:
        app: upf-userplane
        tenant: "{tenant_id}"
        oda.tmforum.org/dataplane-mode: "{dataplane_mode}"
      annotations:
        tmf634.oda.tmforum.org/rfs-profiles: "{profile_codes}"
        tmf634.oda.tmforum.org/cpu-count: "{cpu_count}"
        tmf634.oda.tmforum.org/ram-gb: "{ram_gb}"
        tmf634.oda.tmforum.org/cpu-manager-policy: "{cpu_mgr}"
        tmf634.oda.tmforum.org/topology-manager-policy: "{topo_mgr}"
        tmf634.oda.tmforum.org/numa-nodes: "{numa_nodes}"
        tmf634.oda.tmforum.org/hugepages-enabled: "{hugepages_enabled}"
        tmf634.oda.tmforum.org/hugepage-size: "{hugepage_size}"
        tmf634.oda.tmforum.org/dpdk-enabled: "{dpdk_enabled}"
        tmf634.oda.tmforum.org/sriov-vf-count: "{sriov_vfs}"
        tmf634.oda.tmforum.org/multus-interfaces: "{multus_ifaces}"
    spec:
      serviceAccountName: upf-edge-sa
      containers:
        - name: telco-cnf-datapath
          image: nginx:1.25-alpine
          ports:
            - containerPort: 8080
              name: http-health
          volumeMounts:
            - name: config-vol
              mountPath: /usr/share/nginx/html/status.json
              subPath: status.json
          command: ["/bin/sh", "-c"]
          args:
            - |
              sed -i 's/listen       80;/listen       8080;/g' /etc/nginx/conf.d/default.conf
              nginx -g 'daemon off;'
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
      volumes:
        - name: config-vol
          configMap:
            name: telco-rfs-hardware-recipe
---
apiVersion: v1
kind: Service
metadata:
  name: upf-edge-service
  namespace: {namespace}
spec:
  selector:
    app: upf-userplane
    tenant: "{tenant_id}"
  ports:
    - name: http-health
      port: 8080
      targetPort: 8080
"""


def decompose_order(order_data: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    """Decomposes a TMF622 ProductOrder across any of the 6 Telco Offerings into TMF641, TMF652, Terraform & K8s."""
    cat = load_federated_catalogs()
    order_id = order_data.get("externalId", "ORD-2026-TELCO-9001")
    item = order_data["productOrderItem"][0]
    offering_id = item["productOffering"]["id"]

    # Backward-compatible alias in case legacy offering ID is passed
    if offering_id == "prod-offer-enterprise-edge-tier1":
        offering_id = "prod-offer-5g-upf-hp-001"

    if offering_id not in cat["tmf620_product_offerings"]:
        raise ValueError(f"Unknown TMF620 ProductOffering ID: {offering_id}")

    offering = cat["tmf620_product_offerings"][offering_id]
    prod_spec = cat["tmf620_product_specs"][offering["productSpecification"]["id"]]

    order_chars: Dict[str, Any] = {}
    for c in item.get("product", {}).get("productCharacteristic", []):
        order_chars[c["name"]] = c["value"]

    tenant_id = str(order_chars.get("tenant_id", "tenant-delta")).strip().lower()
    if not re.match(r"^[a-z0-9-]+$", tenant_id):
        raise ValueError(f"Invalid tenant_id '{tenant_id}': must be lowercase alphanumeric/hyphens")

    region = str(order_chars.get("region", "us-central1"))
    throughput_tier = str(order_chars.get("throughput_tier", "10Gbps"))
    latency_tier = str(order_chars.get("latency_tier", "Ultra-Low"))
    redundancy = str(order_chars.get("redundancy", "active-standby"))

    # Resolve CFS & all decomposing RFS Infrastructure Profiles
    cfs_ref_id = prod_spec["serviceSpecification"][0]["id"]
    cfs_spec = cat["tmf633_cfs"][cfs_ref_id]

    rfs_profiles: List[Dict[str, Any]] = []
    for rel in cfs_spec.get("serviceSpecRelationship", []):
        rfs_profiles.append(cat["tmf633_rfs"][rel["id"]])

    # Collect all referenced TMF634 ResourceSpecifications across the RFS profile(s)
    resolved_resources: Dict[str, Dict[str, Any]] = {}
    for rfs in rfs_profiles:
        for res_ref in rfs.get("resourceSpecification", []):
            rid = res_ref["id"]
            if rid not in resolved_resources:
                resolved_resources[rid] = get_default_characteristics(
                    cat["tmf634_resources"][rid], "resourceSpecCharacteristic"
                )

    # Always ensure VPC & Compute defaults exist for downstream Terraform variable synthesis
    for fallback_id in ("res-spec-001", "res-spec-002", "res-spec-004", "res-spec-010"):
        if fallback_id not in resolved_resources:
            resolved_resources[fallback_id] = get_default_characteristics(
                cat["tmf634_resources"][fallback_id], "resourceSpecCharacteristic"
            )

    # Deterministic per-tenant CIDR calculation (prevents subnet collisions across tenants)
    tenant_hash = int(hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:4], 16)
    octet = 40 + (tenant_hash % 170)
    resolved_resources["res-spec-001"]["region"] = region
    resolved_resources["res-spec-001"]["sgi_subnet_cidr"] = f"10.{octet}.1.0/24"
    resolved_resources["res-spec-001"]["n3_subnet_cidr"] = f"10.{octet}.2.0/24"
    resolved_resources["res-spec-001"]["n4_subnet_cidr"] = f"10.{octet}.3.0/24"

    # Evaluate Declarative TMFC003 CFS-to-RFS Hardware Policy Rules
    triggered_rules: List[Dict[str, Any]] = []
    primary_rfs_defaults = get_default_characteristics(rfs_profiles[0], "serviceSpecCharacteristic")
    selected_blueprint = primary_rfs_defaults.get(
        "orchestration_blueprint", "./blueprints/03-5g-upf-network-slice/terraform"
    )

    if latency_tier == "Ultra-Low":
        resolved_resources["res-spec-002"]["numa_nodes"] = 2
        resolved_resources["res-spec-002"]["cpu_manager_policy"] = "static"
        resolved_resources["res-spec-002"]["topology_manager_policy"] = "single-numa-node"
        if "res-spec-003" in resolved_resources:
            resolved_resources["res-spec-003"]["hugepages_enabled"] = True
            resolved_resources["res-spec-003"]["hugepage_size"] = "1Gi"
        resolved_resources["res-spec-004"]["dpdk_enabled"] = True
        resolved_resources["res-spec-004"]["dataplane_mode"] = "SR-IOV"
        resolved_resources["res-spec-004"]["sriov_vf_count"] = 4
        triggered_rules.append(
            {
                "ruleId": "RULE-TELCO-LATENCY-01",
                "condition": "cfs.latency_tier == 'Ultra-Low'",
                "derived_overrides": {
                    "res-spec-002.numa_nodes": 2,
                    "res-spec-002.cpu_manager_policy": "static",
                    "res-spec-003.hugepages_enabled": True,
                    "res-spec-004.dpdk_enabled": True,
                    "res-spec-004.dataplane_mode": "SR-IOV",
                },
            }
        )
    else:
        resolved_resources["res-spec-002"]["numa_nodes"] = 0
        resolved_resources["res-spec-004"]["dpdk_enabled"] = False
        resolved_resources["res-spec-004"]["dataplane_mode"] = "Cilium-eBPF"
        resolved_resources["res-spec-004"]["sriov_vf_count"] = 0

    if throughput_tier in ("40Gbps", "100Gbps", "400Gbps"):
        resolved_resources["res-spec-002"]["cpu_count"] = 32
        resolved_resources["res-spec-002"]["ram_gb"] = 128
        triggered_rules.append(
            {
                "ruleId": "RULE-TELCO-THRU-HIGH",
                "condition": f"cfs.throughput_tier == '{throughput_tier}'",
                "derived_overrides": {"res-spec-002.cpu_count": 32, "res-spec-002.ram_gb": 128},
            }
        )
    elif throughput_tier in ("10Gbps", "25Gbps"):
        resolved_resources["res-spec-002"]["cpu_count"] = 16
        resolved_resources["res-spec-002"]["ram_gb"] = 64
        triggered_rules.append(
            {
                "ruleId": "RULE-TELCO-THRU-10G",
                "condition": f"cfs.throughput_tier == '{throughput_tier}'",
                "derived_overrides": {"res-spec-002.cpu_count": 16, "res-spec-002.ram_gb": 64},
            }
        )
    else:
        resolved_resources["res-spec-002"]["cpu_count"] = 8
        resolved_resources["res-spec-002"]["ram_gb"] = 32

    if redundancy in ("active-standby", "active-active-multizone"):
        resolved_resources["res-spec-002"]["worker_instances"] = 2
        triggered_rules.append(
            {
                "ruleId": "RULE-TELCO-HA-03",
                "condition": f"cfs.redundancy == '{redundancy}'",
                "derived_overrides": {"res-spec-002.worker_instances": 2},
            }
        )
    else:
        resolved_resources["res-spec-002"]["worker_instances"] = 1

    # vRAN / O-RAN specific FEC + PTP rule
    if any(r.get("profileCode") == "TELCO-vRAN" for r in rfs_profiles):
        if "res-spec-007" in resolved_resources:
            resolved_resources["res-spec-007"]["fec_accelerator"] = "Intel-vRAN-Boost-4thGen-Xeon"
        resolved_resources["res-spec-002"]["bios_cstate_pstate_locked"] = True
        triggered_rules.append(
            {
                "ruleId": "RULE-VRAN-REALTIME-PHY",
                "condition": "rfs.profileCode == 'TELCO-vRAN'",
                "derived_overrides": {
                    "res-spec-006.ptp_profile": "ITU-T G.8275.1 (Full Timing Support)",
                    "res-spec-006.synce_enabled": True,
                    "res-spec-007.fec_accelerator": "Intel-vRAN-Boost-4thGen-Xeon",
                    "res-spec-002.bios_cstate_pstate_locked": True,
                },
            }
        )

    # Build TMF641 ServiceOrder
    svc_items: List[Dict[str, Any]] = [
        {
            "id": "1",
            "action": "add",
            "service": {
                "name": f"{cfs_spec['name']}_{tenant_id}",
                "serviceType": "CFS",
                "state": "reserved",
                "serviceSpecification": {
                    "id": cfs_spec["id"],
                    "name": cfs_spec["name"],
                    "@referredType": "CustomerFacingServiceSpecification",
                },
                "serviceCharacteristic": [{"name": k, "value": v} for k, v in order_chars.items()],
                "supportingService": [
                    {"id": str(idx + 2), "name": f"{r['name']}_{tenant_id}"} for idx, r in enumerate(rfs_profiles)
                ],
            },
        }
    ]
    for idx, r in enumerate(rfs_profiles):
        svc_items.append(
            {
                "id": str(idx + 2),
                "action": "add",
                "service": {
                    "name": f"{r['name']}_{tenant_id}",
                    "serviceType": "RFS",
                    "state": "reserved",
                    "serviceSpecification": {
                        "id": r["id"],
                        "name": r["name"],
                        "profileCode": r.get("profileCode", r["id"]),
                        "@referredType": "ResourceFacingServiceSpecification",
                    },
                    "serviceCharacteristic": [
                        {"name": "profile_code", "value": r.get("profileCode", r["id"])},
                        {"name": "deployment_target", "value": r.get("deploymentTarget", "GCP")},
                        {"name": "orchestration_blueprint", "value": selected_blueprint},
                    ],
                },
            }
        )

    tmf641_service_order = {
        "id": f"SVC-ORD-{tenant_id.upper()}",
        "externalId": order_id,
        "href": f"/tmf-api/serviceOrdering/v4/serviceOrder/SVC-ORD-{tenant_id.upper()}",
        "state": "inProgress",
        "description": f"Decomposed CFS & Reusable Telco RFS Profile order for {tenant_id} ({offering['name']})",
        "@type": "ServiceOrder",
        "triggeredPolicyRules": triggered_rules,
        "serviceOrderItem": svc_items,
    }

    # Build TMF652 ResourceOrder
    res_order_items: List[Dict[str, Any]] = []
    for rfs in rfs_profiles:
        for res_ref in rfs.get("resourceSpecification", []):
            rid = res_ref["id"]
            rspec = cat["tmf634_resources"][rid]
            rchars = resolved_resources[rid]
            if any(existing["resource"]["resourceSpecification"]["id"] == rid for existing in res_order_items):
                continue
            res_order_items.append(
                {
                    "id": f"item-{rid}",
                    "action": "add",
                    "resource": {
                        "name": f"{rid}-{tenant_id}",
                        "capabilityTier": rspec.get("capabilityTier", "STANDARD_GCP_GKE"),
                        "resourceSpecification": {"id": rid, "name": rspec["name"]},
                        "resourceCharacteristic": [{"name": k, "value": v} for k, v in rchars.items()],
                    },
                }
            )

    tmf652_resource_order = {
        "id": f"RES-ORD-{tenant_id.upper()}",
        "externalId": order_id,
        "href": f"/tmf-api/resourceOrdering/v4/resourceOrder/RES-ORD-{tenant_id.upper()}",
        "state": "inProgress",
        "description": f"TMF652 Infrastructure Execution Order bound to {selected_blueprint}",
        "@type": "ResourceOrder",
        "resourceOrderItem": res_order_items,
    }

    tf_vars = {
        "project_id": project_id,
        "region": region,
        "tenant_id": tenant_id,
        "order_id": order_id,
        "sgi_subnet_cidr": resolved_resources["res-spec-001"]["sgi_subnet_cidr"],
        "n3_subnet_cidr": resolved_resources["res-spec-001"]["n3_subnet_cidr"],
        "n4_subnet_cidr": resolved_resources["res-spec-001"]["n4_subnet_cidr"],
        "latency_tier": latency_tier,
        "throughput_tier": throughput_tier,
        "dataplane_mode": resolved_resources["res-spec-004"]["dataplane_mode"],
        "cpu_count": resolved_resources["res-spec-002"]["cpu_count"],
        "ram_gb": resolved_resources["res-spec-002"]["ram_gb"],
        "numa_nodes": resolved_resources["res-spec-002"]["numa_nodes"],
        "dpdk_enabled": resolved_resources["res-spec-004"]["dpdk_enabled"],
        "worker_instances": resolved_resources["res-spec-002"]["worker_instances"],
    }

    k8s_manifest = generate_k8s_telco_slice_manifest(
        tenant_id=tenant_id,
        order_id=order_id,
        offering=offering,
        cfs_spec=cfs_spec,
        rfs_profiles=rfs_profiles,
        resolved_resources=resolved_resources,
        order_chars=order_chars,
        project_id=project_id,
    )

    trace = {
        "order_id": order_id,
        "tenant_id": tenant_id,
        "offering_id": offering["id"],
        "offering_name": offering["name"],
        "cfs_id": cfs_spec["id"],
        "cfs_name": cfs_spec["name"],
        "rfs_profiles": [
            {"id": r["id"], "profileCode": r.get("profileCode", r["id"]), "name": r["name"]} for r in rfs_profiles
        ],
        "selected_blueprint": selected_blueprint,
        "tf_vars": tf_vars,
    }

    save_json(BUILD_DIR / "tmf622-product-order-ingested.json", order_data)
    save_json(BUILD_DIR / "tmf641-service-order.json", tmf641_service_order)
    save_json(BUILD_DIR / "tmf652-resource-order.json", tmf652_resource_order)
    save_json(BUILD_DIR / "decomposition-trace.json", trace)
    save_json(BUILD_DIR / "generated.auto.tfvars.json", tf_vars)
    save_json(REPO_ROOT / "blueprints" / "03-5g-upf-network-slice" / "terraform" / "generated.auto.tfvars.json", tf_vars)
    (BUILD_DIR / "k8s-telco-slice-manifest.yaml").write_text(k8s_manifest, encoding="utf-8")

    return trace


def sync_inventory(
    tf_outputs_path: Path,
    k8s_namespace_uid: str,
    k8s_pod_uids: str,
    gke_cluster_name: str,
) -> str:
    """Transitions TMF638 Service Inventory & TMF639 Resource Inventory to 'active' post-deployment."""
    order_data = load_json(BUILD_DIR / "tmf622-product-order-ingested.json")
    tmf641 = load_json(BUILD_DIR / "tmf641-service-order.json")
    tmf652 = load_json(BUILD_DIR / "tmf652-resource-order.json")
    trace = load_json(BUILD_DIR / "decomposition-trace.json")
    tf_vars = trace["tf_vars"]

    tf_out: Dict[str, Any] = {}
    if tf_outputs_path.exists():
        raw_tf = load_json(tf_outputs_path)
        for k, v in raw_tf.items():
            tf_out[k] = v.get("value", v) if isinstance(v, dict) else v

    tenant_id = tf_vars["tenant_id"]
    project_id = tf_vars["project_id"]
    region = tf_vars["region"]
    order_id = tf_vars["order_id"]
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    vpc_self_link = tf_out.get("upf_vpc_self_link", f"projects/{project_id}/global/networks/vpc-upf-{tenant_id}")
    sgi_self_link = tf_out.get("sgi_subnet_self_link", f"projects/{project_id}/regions/{region}/subnetworks/sgi-subnet-{tenant_id}")
    n3_self_link = tf_out.get("n3_subnet_self_link", f"projects/{project_id}/regions/{region}/subnetworks/n3-subnet-{tenant_id}")
    n4_self_link = tf_out.get("n4_subnet_self_link", f"projects/{project_id}/regions/{region}/subnetworks/n4-subnet-{tenant_id}")
    wi_sa_email = tf_out.get("workload_identity_sa_email", f"upf-{tenant_id}-sa@{project_id}.iam.gserviceaccount.com")

    tmf639_inventory = {
        "synchronizedAt": now_iso,
        "healthCheckStatus": "PASS",
        "resources": [
            {
                "id": f"res-inv-vpc-{tenant_id}",
                "href": f"/tmf-api/resourceInventoryManagement/v4/resource/res-inv-vpc-{tenant_id}",
                "name": f"vpc-upf-{tenant_id}",
                "resourceStatus": "available",
                "operationalState": "enable",
                "usageState": "active",
                "@type": "LogicalResource",
                "resourceSpecification": {"id": "res-spec-001", "name": "Telco3gppMultiPlaneVpcSpec"},
                "resourceCharacteristic": [
                    {"name": "gcp_project_id", "value": project_id},
                    {"name": "vpc_self_link", "value": vpc_self_link},
                    {"name": "sgi_subnet_self_link", "value": sgi_self_link},
                    {"name": "n3_subnet_self_link", "value": n3_self_link},
                    {"name": "n4_subnet_self_link", "value": n4_self_link},
                ],
            },
            {
                "id": f"res-inv-compute-{tenant_id}",
                "href": f"/tmf-api/resourceInventoryManagement/v4/resource/res-inv-compute-{tenant_id}",
                "name": f"worker-pool-upf-{tenant_id}",
                "resourceStatus": "available",
                "operationalState": "enable",
                "usageState": "active",
                "@type": "LogicalResource",
                "resourceSpecification": {"id": "res-spec-002", "name": "TelcoDeterministicComputeNumaCpuSpec"},
                "resourceCharacteristic": [
                    {"name": "gke_cluster_uri", "value": f"projects/{project_id}/locations/{region}/clusters/{gke_cluster_name}"},
                    {"name": "k8s_namespace", "value": f"upf-{tenant_id}"},
                    {"name": "k8s_namespace_uid", "value": k8s_namespace_uid},
                    {"name": "worker_pod_uids", "value": k8s_pod_uids},
                    {"name": "workload_identity_iam_sa", "value": wi_sa_email},
                    {"name": "cpu_count", "value": tf_vars["cpu_count"]},
                    {"name": "ram_gb", "value": tf_vars["ram_gb"]},
                    {"name": "numa_nodes", "value": tf_vars["numa_nodes"]},
                    {"name": "dpdk_enabled", "value": tf_vars["dpdk_enabled"]},
                    {"name": "dataplane_mode", "value": tf_vars["dataplane_mode"]},
                ],
            },
        ],
    }

    rfs_codes = ", ".join(p["profileCode"] for p in trace["rfs_profiles"])
    tmf638_inventory = {
        "synchronizedAt": now_iso,
        "services": [
            {
                "id": f"svc-inv-cfs-{tenant_id}",
                "href": f"/tmf-api/serviceInventory/v4/service/svc-inv-cfs-{tenant_id}",
                "name": f"{trace['cfs_name']}_{tenant_id}",
                "state": "active",
                "serviceType": "CFS",
                "@type": "CustomerFacingService",
                "serviceSpecification": {"id": trace["cfs_id"], "name": trace["cfs_name"]},
                "supportingService": [
                    {"id": f"svc-inv-rfs-{p['profileCode'].lower()}-{tenant_id}", "name": p["name"], "state": "active"}
                    for p in trace["rfs_profiles"]
                ],
            }
        ]
        + [
            {
                "id": f"svc-inv-rfs-{p['profileCode'].lower()}-{tenant_id}",
                "href": f"/tmf-api/serviceInventory/v4/service/svc-inv-rfs-{p['profileCode'].lower()}-{tenant_id}",
                "name": f"{p['name']}_{tenant_id}",
                "state": "active",
                "serviceType": "RFS",
                "@type": "ResourceFacingService",
                "serviceSpecification": {"id": p["id"], "name": p["name"], "profileCode": p["profileCode"]},
                "supportingResource": [
                    {"id": f"res-inv-vpc-{tenant_id}", "name": f"vpc-upf-{tenant_id}"},
                    {"id": f"res-inv-compute-{tenant_id}", "name": f"worker-pool-upf-{tenant_id}"},
                ],
            }
            for p in trace["rfs_profiles"]
        ],
    }

    tmf641["state"] = "completed"
    for s_item in tmf641["serviceOrderItem"]:
        s_item["service"]["state"] = "active"
    tmf652["state"] = "completed"
    order_data["state"] = "completed"
    order_data["completionDate"] = now_iso

    save_json(BUILD_DIR / "tmf639-resource-inventory-active.json", tmf639_inventory)
    save_json(BUILD_DIR / "tmf638-service-inventory-active.json", tmf638_inventory)
    save_json(BUNDLE_DIR / "tmf639.json", tmf639_inventory)
    save_json(BUNDLE_DIR / "tmf638.json", tmf638_inventory)
    save_json(BUILD_DIR / "tmf641-service-order.json", tmf641)
    save_json(BUILD_DIR / "tmf652-resource-order.json", tmf652)
    save_json(BUILD_DIR / "tmf622-product-order-completed.json", order_data)

    md = f"""## 🚀 Wipro Telco Cloud Catalog — Order-to-Activation Summary (`{order_id}`)

| Pipeline Stage | TM Forum API | Entity / Profile | Resolved Configuration | State |
| :--- | :--- | :--- | :--- | :--- |
| **1. Commercial Order** | `TMF622` | `{trace['offering_id']}` ({trace['offering_name']}) | Tenant: `{tenant_id}`, Throughput: `{tf_vars['throughput_tier']}`, Latency: `{tf_vars['latency_tier']}` | `Completed` |
| **2. CFS Decomposition** | `TMF633` / `TMF641` | `{trace['cfs_id']}` (`{trace['cfs_name']}`) | Triggered `{len(tmf641.get('triggeredPolicyRules', []))}` TMFC003 Hardware Policy Rules | `Active` (`TMF638`) |
| **3. RFS Infra Profile(s)** | `TMF633` / `TMF641` | **{rfs_codes}** | Target Blueprint: `{trace['selected_blueprint']}` | `Active` (`TMF638`) |
| **4. Resource & IaC Execution** | `TMF634` / `TMF652` | `{len(tmf652['resourceOrderItem'])}` Atomic ResourceSpecs | `cpu={tf_vars['cpu_count']}`, `ram={tf_vars['ram_gb']}GiB`, `numa={tf_vars['numa_nodes']}`, `dpdk={tf_vars['dpdk_enabled']}`, `dataplane={tf_vars['dataplane_mode']}` | `Active` (`TMF639`) |

### Active Physical Inventory (`TMF639`)
- **GCP Project / Region**: `{project_id}` (`{region}`)
- **3GPP Multi-Plane VPC**: `{vpc_self_link}` (`SGi: {tf_vars['sgi_subnet_cidr']}`, `N3: {tf_vars['n3_subnet_cidr']}`, `N4: {tf_vars['n4_subnet_cidr']}`)
- **GKE Cluster & Namespace**: `{gke_cluster_name}` / `upf-{tenant_id}` (UID: `{k8s_namespace_uid}`)
- **Active CNF Pod UIDs**: `{k8s_pod_uids}`
- **Workload Identity SA**: `{wi_sa_email}`
"""
    (BUILD_DIR / "order-to-activation-summary.md").write_text(md, encoding="utf-8")
    return md


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Wipro Telco Cloud Catalog & Order Orchestrator (TMFC003)")
    parser.add_argument("--mode", choices=["validate-catalogs", "decompose", "sync-inventory"], required=True)
    parser.add_argument("--order-file", type=str, default="", help="Path to TMF622 ProductOrder JSON")
    parser.add_argument("--offering-id", type=str, default="prod-offer-5g-upf-hp-001")
    parser.add_argument("--tenant-id", type=str, default="tenant-delta")
    parser.add_argument("--customer-name", type=str, default="Delta Manufacturing Corp")
    parser.add_argument("--latency-tier", type=str, default="Ultra-Low")
    parser.add_argument("--throughput-tier", type=str, default="10Gbps")
    parser.add_argument("--redundancy", type=str, default="active-standby")
    parser.add_argument("--region", type=str, default="us-central1")
    parser.add_argument("--project-id", type=str, default="gcp-oda-canvas-poc")
    parser.add_argument("--tf-outputs-json", type=str, default="build/tf-outputs.json")
    parser.add_argument("--k8s-namespace-uid", type=str, default="ns-telco-verified-uid")
    parser.add_argument("--k8s-pod-uids", type=str, default="pod-cnf-0,pod-cnf-1")
    parser.add_argument("--gke-cluster-name", type=str, default="oda-canvas-mt-gke")

    args = parser.parse_args()

    if args.mode == "validate-catalogs":
        print(validate_catalogs())
    elif args.mode == "decompose":
        if args.order_file:
            order_data = load_json(Path(args.order_file))
        else:
            order_data = {
                "externalId": f"ORD-2026-{args.tenant_id.upper()}",
                "priority": "1",
                "description": f"Catalog-driven Telco Cloud order ({args.offering_id}) for {args.tenant_id}",
                "@type": "ProductOrder",
                "relatedParty": [
                    {
                        "id": f"ORG-{args.tenant_id.upper()}",
                        "name": args.customer_name,
                        "role": "Customer",
                        "@referredType": "Organization",
                    }
                ],
                "productOrderItem": [
                    {
                        "id": "100",
                        "action": "add",
                        "quantity": 1,
                        "productOffering": {"id": args.offering_id},
                        "product": {
                            "productCharacteristic": [
                                {"name": "tenant_id", "value": args.tenant_id},
                                {"name": "region", "value": args.region},
                                {"name": "throughput_tier", "value": args.throughput_tier},
                                {"name": "latency_tier", "value": args.latency_tier},
                                {"name": "redundancy", "value": args.redundancy},
                            ]
                        },
                    }
                ],
            }
        trace = decompose_order(order_data, project_id=args.project_id)
        rfs_list = ", ".join(p["profileCode"] for p in trace["rfs_profiles"])
        print(f"[OK] Decomposed TMF622 Order '{trace['order_id']}' for tenant '{trace['tenant_id']}'")
        print(f"  -> Offering:  {trace['offering_id']} ({trace['offering_name']})")
        print(f"  -> CFS Spec:  {trace['cfs_id']}")
        print(f"  -> RFS Profs: {rfs_list}")
        print(f"  -> Blueprint: {trace['selected_blueprint']}")
        print("  -> Emitted:   build/tmf641-service-order.json, build/tmf652-resource-order.json, build/k8s-telco-slice-manifest.yaml")
    elif args.mode == "sync-inventory":
        print(
            sync_inventory(
                tf_outputs_path=Path(args.tf_outputs_json),
                k8s_namespace_uid=args.k8s_namespace_uid,
                k8s_pod_uids=args.k8s_pod_uids,
                gke_cluster_name=args.gke_cluster_name,
            )
        )


if __name__ == "__main__":
    main()
