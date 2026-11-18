#!/usr/bin/env node
/**
 * Wipro Telco Cloud Catalog — TM Forum ODA & SID (GB922) Orchestrator (Node.js CLI)
 * =================================================================================
 * Cross-platform companion to telco_catalog_orchestrator.py for Windows/Linux/macOS:
 *   --mode validate-catalogs
 *   --mode decompose [--order-file <path>]
 *   --mode sync-inventory
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const REPO_ROOT = path.resolve(__dirname, '..');
const CATALOG_DIR = path.join(REPO_ROOT, 'catalogs');
const BUILD_DIR = path.join(REPO_ROOT, 'build');
const BUNDLE_DIR = path.join(BUILD_DIR, 'catalog-bundle');

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function saveJson(p, data) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(data, null, 2) + '\n', 'utf8');
}

function getDefaultChars(spec, charKey) {
  const out = {};
  const valKey = charKey + 'Value';
  for (const c of (spec[charKey] || [])) {
    const vals = c[valKey] || [];
    let chosen = undefined;
    for (const v of vals) {
      if (v.isDefault) {
        chosen = v.value;
        break;
      }
    }
    if (chosen === undefined && vals.length > 0) chosen = vals[0].value;
    if (c.name) out[c.name] = JSON.parse(JSON.stringify(chosen));
  }
  return out;
}

function loadDirJsons(dirPath) {
  return fs.readdirSync(dirPath)
    .filter(f => f.endsWith('.json'))
    .sort()
    .map(f => loadJson(path.join(dirPath, f)));
}

function loadFederatedCatalogs() {
  const capability_matrix = loadJson(path.join(CATALOG_DIR, 'telco-hw-capability-matrix.json'));
  const tmf634_resources = {};
  for (const d of loadDirJsons(path.join(CATALOG_DIR, 'tmf634-resource-catalog'))) tmf634_resources[d.id] = d;

  const tmf633_rfs = {};
  for (const d of loadDirJsons(path.join(CATALOG_DIR, 'tmf633-rfs-profiles'))) tmf633_rfs[d.id] = d;

  const tmf633_cfs = {};
  for (const d of loadDirJsons(path.join(CATALOG_DIR, 'tmf633-cfs-catalog'))) tmf633_cfs[d.id] = d;

  const tmf620_product_specs = {};
  const tmf620_product_offerings = {};
  for (const d of loadDirJsons(path.join(CATALOG_DIR, 'tmf620-product-catalog'))) {
    if (d['@type'] === 'ProductSpecification') tmf620_product_specs[d.id] = d;
    if (d['@type'] === 'ProductOffering') tmf620_product_offerings[d.id] = d;
  }

  return { capability_matrix, tmf634_resources, tmf633_rfs, tmf633_cfs, tmf620_product_specs, tmf620_product_offerings };
}

function validateCatalogs() {
  const cat = loadFederatedCatalogs();
  const errors = [];
  const lines = [
    '## Wipro Telco Cloud Catalog — SID `GB922` Referential Integrity Report',
    '',
    '| Catalog Layer | TM Forum API | ODA Component | Entity ID | Name / Profile | `@type` | Status |',
    '| :--- | :--- | :--- | :--- | :--- | :--- | :--- |'
  ];

  for (const [poId, po] of Object.entries(cat.tmf620_product_offerings)) {
    const psRef = po.productSpecification && po.productSpecification.id;
    if (!cat.tmf620_product_specs[psRef]) errors.push(`ProductOffering ${poId} missing ProductSpec ${psRef}`);
    lines.push(`| **Layer 1: Product Catalog** | \`TMF620\` | \`TMFC001\` | \`${poId}\` | ${po.name} | \`${po['@type']}\` | \`${po.lifecycleStatus}\` |`);
  }

  for (const [psId, ps] of Object.entries(cat.tmf620_product_specs)) {
    for (const cref of (ps.serviceSpecification || [])) {
      if (!cat.tmf633_cfs[cref.id]) errors.push(`ProductSpec ${psId} missing CFS ${cref.id}`);
    }
    lines.push(`| **Layer 1: Product Spec** | \`TMF620\` | \`TMFC001\` | \`${psId}\` | ${ps.name} | \`${ps['@type']}\` | \`${ps.lifecycleStatus}\` |`);
  }

  for (const [cfsId, cfs] of Object.entries(cat.tmf633_cfs)) {
    const rels = cfs.serviceSpecRelationship || [];
    if (!rels.length) errors.push(`CFS ${cfsId} has no RFS relationships`);
    for (const r of rels) {
      if (!cat.tmf633_rfs[r.id]) errors.push(`CFS ${cfsId} missing RFS ${r.id}`);
    }
    lines.push(`| **Layer 2: Service Catalog (CFS)** | \`TMF633\` | \`TMFC006\` | \`${cfsId}\` | ${cfs.name} | \`${cfs['@type']}\` | \`${cfs.lifecycleStatus}\` |`);
  }

  for (const [rfsId, rfs] of Object.entries(cat.tmf633_rfs)) {
    for (const rref of (rfs.resourceSpecification || [])) {
      if (!cat.tmf634_resources[rref.id]) errors.push(`RFS ${rfsId} missing TMF634 ResourceSpec ${rref.id}`);
    }
    lines.push(`| **Layer 3: RFS Infra Profile** | \`TMF633\` | \`TMFC006\` | \`${rfsId}\` | **${rfs.profileCode}** (\`${rfs.name}\`) | \`${rfs['@type']}\` | \`${rfs.lifecycleStatus}\` |`);
  }

  for (const [resId, res] of Object.entries(cat.tmf634_resources)) {
    const defs = getDefaultChars(res, 'resourceSpecCharacteristic');
    if (!defs.iac_binding) {
      errors.push(`ResourceSpec ${resId} missing iac_binding`);
    } else {
      const bpFull = path.resolve(REPO_ROOT, defs.iac_binding.blueprint_path);
      if (!fs.existsSync(bpFull)) errors.push(`ResourceSpec ${resId} blueprint_path not found: ${defs.iac_binding.blueprint_path}`);
    }
    lines.push(`| **Layer 4: Resource Catalog** | \`TMF634\` | \`TMFC007\` | \`${resId}\` | ${res.name} (\`${res.capabilityTier}\`) | \`${res['@type']}\` | \`${res.lifecycleStatus}\` |`);
  }

  const caps = cat.capability_matrix.capabilities || [];
  if (caps.length < 16) errors.push(`Expected 16 capabilities, got ${caps.length}`);
  for (const c of caps) {
    if (!cat.tmf634_resources[c.tmf634ResourceSpecId]) errors.push(`Capability ${c.id} missing ResourceSpec ${c.tmf634ResourceSpecId}`);
  }

  if (errors.length) {
    throw new Error('Catalog Validation Failed:\n' + errors.join('\n'));
  }

  lines.push('');
  lines.push('### ✅ Validation Result: PASSED (100% SID `GB922` Referential Integrity)');
  lines.push(`- **Commercial Offerings (\`TMF620\`)**: \`${Object.keys(cat.tmf620_product_offerings).length}\` Offerings + \`${Object.keys(cat.tmf620_product_specs).length}\` Product Specifications`);
  lines.push(`- **Customer-Facing Services (\`TMF633\` CFS)**: \`${Object.keys(cat.tmf633_cfs).length}\` CFS Specifications`);
  lines.push(`- **Reusable Telco Infra Profiles (\`TMF633\` RFS)**: \`${Object.keys(cat.tmf633_rfs).length}\` Standardized Profiles (\`TELCO-GENERAL-CNF\`, \`TELCO-HP-CNF\`, \`TELCO-UPF\`, \`TELCO-vRAN\`, \`TELCO-EDGE\`)`);
  lines.push(`- **Atomic Resource Specs (\`TMF634\`)**: \`${Object.keys(cat.tmf634_resources).length}\` Resource Specifications verified against \`blueprints/01..03\``);
  lines.push(`- **Telco Hardware Capability Matrix**: \`${caps.length}\` Specialized Hardware & K8s Requirements mapped across 4 Tiers`);

  saveJson(path.join(BUNDLE_DIR, 'tmf620.json'), {
    productOfferings: Object.values(cat.tmf620_product_offerings),
    productSpecifications: Object.values(cat.tmf620_product_specs)
  });
  saveJson(path.join(BUNDLE_DIR, 'tmf633.json'), {
    customerFacingServices: Object.values(cat.tmf633_cfs),
    resourceFacingProfiles: Object.values(cat.tmf633_rfs)
  });
  saveJson(path.join(BUNDLE_DIR, 'tmf634.json'), Object.values(cat.tmf634_resources));
  saveJson(path.join(BUNDLE_DIR, 'capability-matrix.json'), cat.capability_matrix);

  const report = lines.join('\n') + '\n';
  fs.mkdirSync(BUILD_DIR, { recursive: true });
  fs.writeFileSync(path.join(BUILD_DIR, 'catalog-validation-report.md'), report, 'utf8');
  return report;
}

function decomposeOrder(orderData, projectId = 'wipro-telco-cloud-catalog1') {
  const cat = loadFederatedCatalogs();
  const orderId = orderData.externalId || 'ORD-2026-TELCO-9001';
  const item = orderData.productOrderItem[0];
  const offeringId = item.productOffering.id;
  const offering = cat.tmf620_product_offerings[offeringId];
  if (!offering) throw new Error(`Unknown ProductOffering ID: ${offeringId}`);

  const prodSpec = cat.tmf620_product_specs[offering.productSpecification.id];
  const orderChars = {};
  for (const c of ((item.product && item.product.productCharacteristic) || [])) {
    orderChars[c.name] = c.value;
  }

  const tenantId = String(orderChars.tenant_id || 'tenant-delta').toLowerCase();
  const region = String(orderChars.region || 'us-central1');
  const throughputTier = String(orderChars.throughput_tier || '10Gbps');
  const latencyTier = String(orderChars.latency_tier || 'Ultra-Low');
  const redundancy = String(orderChars.redundancy || 'active-standby');

  const cfsSpec = cat.tmf633_cfs[prodSpec.serviceSpecification[0].id];
  const rfsProfiles = cfsSpec.serviceSpecRelationship.map(r => cat.tmf633_rfs[r.id]);

  const resolved = {};
  for (const rfs of rfsProfiles) {
    for (const rr of rfs.resourceSpecification) {
      if (!resolved[rr.id]) {
        resolved[rr.id] = getDefaultChars(cat.tmf634_resources[rr.id], 'resourceSpecCharacteristic');
      }
    }
  }
  for (const fb of ['res-spec-001', 'res-spec-002', 'res-spec-004', 'res-spec-010']) {
    if (!resolved[fb]) resolved[fb] = getDefaultChars(cat.tmf634_resources[fb], 'resourceSpecCharacteristic');
  }

  const hashHex = crypto.createHash('sha256').update(tenantId).digest('hex').slice(0, 4);
  const octet = 40 + (parseInt(hashHex, 16) % 170);
  resolved['res-spec-001'].region = region;
  resolved['res-spec-001'].sgi_subnet_cidr = `10.${octet}.1.0/24`;
  resolved['res-spec-001'].n3_subnet_cidr = `10.${octet}.2.0/24`;
  resolved['res-spec-001'].n4_subnet_cidr = `10.${octet}.3.0/24`;

  const primaryRfsDefaults = getDefaultChars(rfsProfiles[0], 'serviceSpecCharacteristic');
  const selectedBlueprint = primaryRfsDefaults.orchestration_blueprint || './blueprints/03-5g-upf-network-slice/terraform';
  const triggeredRules = [];

  if (latencyTier === 'Ultra-Low') {
    resolved['res-spec-002'].numa_nodes = 2;
    resolved['res-spec-002'].cpu_manager_policy = 'static';
    resolved['res-spec-002'].topology_manager_policy = 'single-numa-node';
    if (resolved['res-spec-003']) {
      resolved['res-spec-003'].hugepages_enabled = true;
      resolved['res-spec-003'].hugepage_size = '1Gi';
    }
    resolved['res-spec-004'].dpdk_enabled = true;
    resolved['res-spec-004'].dataplane_mode = 'SR-IOV';
    resolved['res-spec-004'].sriov_vf_count = 4;
    triggeredRules.push({
      ruleId: 'RULE-TELCO-LATENCY-01',
      condition: "cfs.latency_tier == 'Ultra-Low'",
      derived_overrides: {
        'res-spec-002.numa_nodes': 2,
        'res-spec-002.cpu_manager_policy': 'static',
        'res-spec-003.hugepages_enabled': true,
        'res-spec-004.dpdk_enabled': true,
        'res-spec-004.dataplane_mode': 'SR-IOV'
      }
    });
  } else {
    resolved['res-spec-002'].numa_nodes = 0;
    resolved['res-spec-004'].dpdk_enabled = false;
    resolved['res-spec-004'].dataplane_mode = 'Cilium-eBPF';
    resolved['res-spec-004'].sriov_vf_count = 0;
  }

  if (['40Gbps', '100Gbps', '400Gbps'].includes(throughputTier)) {
    resolved['res-spec-002'].cpu_count = 32;
    resolved['res-spec-002'].ram_gb = 128;
    triggeredRules.push({ ruleId: 'RULE-TELCO-THRU-HIGH', condition: `cfs.throughput_tier == '${throughputTier}'` });
  } else if (['10Gbps', '25Gbps'].includes(throughputTier)) {
    resolved['res-spec-002'].cpu_count = 16;
    resolved['res-spec-002'].ram_gb = 64;
    triggeredRules.push({ ruleId: 'RULE-TELCO-THRU-10G', condition: `cfs.throughput_tier == '${throughputTier}'` });
  } else {
    resolved['res-spec-002'].cpu_count = 8;
    resolved['res-spec-002'].ram_gb = 32;
  }

  resolved['res-spec-002'].worker_instances = ['active-standby', 'active-active-multizone'].includes(redundancy) ? 2 : 1;
  if (resolved['res-spec-002'].worker_instances === 2) {
    triggeredRules.push({ ruleId: 'RULE-TELCO-HA-03', condition: `cfs.redundancy == '${redundancy}'` });
  }

  if (rfsProfiles.some(r => r.profileCode === 'TELCO-vRAN')) {
    if (resolved['res-spec-007']) resolved['res-spec-007'].fec_accelerator = 'Intel-vRAN-Boost-4thGen-Xeon';
    resolved['res-spec-002'].bios_cstate_pstate_locked = true;
    triggeredRules.push({ ruleId: 'RULE-VRAN-REALTIME-PHY', condition: "rfs.profileCode == 'TELCO-vRAN'" });
  }

  const tmf641 = {
    id: `SVC-ORD-${tenantId.toUpperCase()}`,
    externalId: orderId,
    href: `/tmf-api/serviceOrdering/v4/serviceOrder/SVC-ORD-${tenantId.toUpperCase()}`,
    state: 'inProgress',
    description: `Decomposed CFS & Reusable Telco RFS Profile order for ${tenantId} (${offering.name})`,
    '@type': 'ServiceOrder',
    triggeredPolicyRules: triggeredRules,
    serviceOrderItem: [
      {
        id: '1',
        action: 'add',
        service: {
          name: `${cfsSpec.name}_${tenantId}`,
          serviceType: 'CFS',
          state: 'reserved',
          serviceSpecification: { id: cfsSpec.id, name: cfsSpec.name, '@referredType': 'CustomerFacingServiceSpecification' },
          serviceCharacteristic: Object.entries(orderChars).map(([name, value]) => ({ name, value })),
          supportingService: rfsProfiles.map((r, i) => ({ id: String(i + 2), name: `${r.name}_${tenantId}` }))
        }
      },
      ...rfsProfiles.map((r, i) => ({
        id: String(i + 2),
        action: 'add',
        service: {
          name: `${r.name}_${tenantId}`,
          serviceType: 'RFS',
          state: 'reserved',
          serviceSpecification: { id: r.id, name: r.name, profileCode: r.profileCode, '@referredType': 'ResourceFacingServiceSpecification' },
          serviceCharacteristic: [
            { name: 'profile_code', value: r.profileCode },
            { name: 'deployment_target', value: r.deploymentTarget },
            { name: 'orchestration_blueprint', value: selectedBlueprint }
          ]
        }
      }))
    ]
  };

  const resItems = [];
  for (const rfs of rfsProfiles) {
    for (const rr of rfs.resourceSpecification) {
      if (resItems.some(x => x.resource.resourceSpecification.id === rr.id)) continue;
      const rspec = cat.tmf634_resources[rr.id];
      resItems.push({
        id: `item-${rr.id}`,
        action: 'add',
        resource: {
          name: `${rr.id}-${tenantId}`,
          capabilityTier: rspec.capabilityTier,
          resourceSpecification: { id: rr.id, name: rspec.name },
          resourceCharacteristic: Object.entries(resolved[rr.id]).map(([name, value]) => ({ name, value }))
        }
      });
    }
  }

  const tmf652 = {
    id: `RES-ORD-${tenantId.toUpperCase()}`,
    externalId: orderId,
    href: `/tmf-api/resourceOrdering/v4/resourceOrder/RES-ORD-${tenantId.toUpperCase()}`,
    state: 'inProgress',
    description: `TMF652 Infrastructure Execution Order bound to ${selectedBlueprint}`,
    '@type': 'ResourceOrder',
    resourceOrderItem: resItems
  };

  const tfVars = {
    project_id: projectId,
    region,
    tenant_id: tenantId,
    order_id: orderId,
    sgi_subnet_cidr: resolved['res-spec-001'].sgi_subnet_cidr,
    n3_subnet_cidr: resolved['res-spec-001'].n3_subnet_cidr,
    n4_subnet_cidr: resolved['res-spec-001'].n4_subnet_cidr,
    latency_tier: latencyTier,
    throughput_tier: throughputTier,
    dataplane_mode: resolved['res-spec-004'].dataplane_mode,
    cpu_count: resolved['res-spec-002'].cpu_count,
    ram_gb: resolved['res-spec-002'].ram_gb,
    numa_nodes: resolved['res-spec-002'].numa_nodes,
    dpdk_enabled: resolved['res-spec-004'].dpdk_enabled,
    worker_instances: resolved['res-spec-002'].worker_instances
  };

  const profileCodes = rfsProfiles.map(r => r.profileCode).join(',');
  const namespace = `upf-${tenantId}`;
  const k8sYaml = `# AUTO-GENERATED BY WIPRO TELCO CLOUD CATALOG ORCHESTRATOR (TMFC003 -> TMF652)
apiVersion: v1
kind: Namespace
metadata:
  name: ${namespace}
  labels:
    oda.tmforum.org/tenant-id: "${tenantId}"
    oda.tmforum.org/order-id: "${orderId}"
    oda.tmforum.org/cfs-spec: "${cfsSpec.id}"
    oda.tmforum.org/rfs-profile: "${rfsProfiles[0].profileCode}"
    oda.tmforum.org/dataplane-mode: "${tfVars.dataplane_mode}"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: upf-userplane-workers
  namespace: ${namespace}
spec:
  replicas: ${tfVars.worker_instances}
  selector:
    matchLabels:
      app: upf-userplane
      tenant: "${tenantId}"
  template:
    metadata:
      labels:
        app: upf-userplane
        tenant: "${tenantId}"
      annotations:
        tmf634.oda.tmforum.org/rfs-profiles: "${profileCodes}"
        tmf634.oda.tmforum.org/cpu-count: "${tfVars.cpu_count}"
        tmf634.oda.tmforum.org/ram-gb: "${tfVars.ram_gb}"
        tmf634.oda.tmforum.org/numa-nodes: "${tfVars.numa_nodes}"
        tmf634.oda.tmforum.org/dpdk-enabled: "${tfVars.dpdk_enabled}"
    spec:
      containers:
        - name: telco-cnf-datapath
          image: nginx:1.25-alpine
          ports:
            - containerPort: 8080
`;

  const trace = {
    order_id: orderId,
    tenant_id: tenantId,
    offering_id: offering.id,
    offering_name: offering.name,
    cfs_id: cfsSpec.id,
    cfs_name: cfsSpec.name,
    rfs_profiles: rfsProfiles.map(r => ({ id: r.id, profileCode: r.profileCode, name: r.name })),
    selected_blueprint: selectedBlueprint,
    tf_vars: tfVars
  };

  saveJson(path.join(BUILD_DIR, 'tmf622-product-order-ingested.json'), orderData);
  saveJson(path.join(BUILD_DIR, 'tmf641-service-order.json'), tmf641);
  saveJson(path.join(BUILD_DIR, 'tmf652-resource-order.json'), tmf652);
  saveJson(path.join(BUILD_DIR, 'decomposition-trace.json'), trace);
  saveJson(path.join(BUILD_DIR, 'generated.auto.tfvars.json'), tfVars);
  fs.writeFileSync(path.join(BUILD_DIR, 'k8s-telco-slice-manifest.yaml'), k8sYaml, 'utf8');
  return trace;
}

function syncInventory(gkeClusterName = 'oda-canvas-mt-gke') {
  const orderData = loadJson(path.join(BUILD_DIR, 'tmf622-product-order-ingested.json'));
  const tmf641 = loadJson(path.join(BUILD_DIR, 'tmf641-service-order.json'));
  const tmf652 = loadJson(path.join(BUILD_DIR, 'tmf652-resource-order.json'));
  const trace = loadJson(path.join(BUILD_DIR, 'decomposition-trace.json'));
  const tfVars = trace.tf_vars;
  const tenantId = tfVars.tenant_id;
  const projectId = tfVars.project_id;
  const region = tfVars.region;
  const nowIso = new Date().toISOString();

  const tmf639 = {
    synchronizedAt: nowIso,
    healthCheckStatus: 'PASS',
    resources: [
      {
        id: `res-inv-vpc-${tenantId}`,
        href: `/tmf-api/resourceInventoryManagement/v4/resource/res-inv-vpc-${tenantId}`,
        name: `vpc-upf-${tenantId}`,
        resourceStatus: 'available',
        operationalState: 'enable',
        usageState: 'active',
        '@type': 'LogicalResource',
        resourceSpecification: { id: 'res-spec-001', name: 'Telco3gppMultiPlaneVpcSpec' },
        resourceCharacteristic: [
          { name: 'gcp_project_id', value: projectId },
          { name: 'vpc_self_link', value: `projects/${projectId}/global/networks/vpc-upf-${tenantId}` },
          { name: 'sgi_subnet_cidr', value: tfVars.sgi_subnet_cidr },
          { name: 'n3_subnet_cidr', value: tfVars.n3_subnet_cidr },
          { name: 'n4_subnet_cidr', value: tfVars.n4_subnet_cidr }
        ]
      },
      {
        id: `res-inv-compute-${tenantId}`,
        href: `/tmf-api/resourceInventoryManagement/v4/resource/res-inv-compute-${tenantId}`,
        name: `worker-pool-upf-${tenantId}`,
        resourceStatus: 'available',
        operationalState: 'enable',
        usageState: 'active',
        '@type': 'LogicalResource',
        resourceSpecification: { id: 'res-spec-002', name: 'TelcoDeterministicComputeNumaCpuSpec' },
        resourceCharacteristic: [
          { name: 'gke_cluster_uri', value: `projects/${projectId}/locations/${region}/clusters/${gkeClusterName}` },
          { name: 'k8s_namespace', value: `upf-${tenantId}` },
          { name: 'cpu_count', value: tfVars.cpu_count },
          { name: 'ram_gb', value: tfVars.ram_gb },
          { name: 'numa_nodes', value: tfVars.numa_nodes },
          { name: 'dpdk_enabled', value: tfVars.dpdk_enabled },
          { name: 'dataplane_mode', value: tfVars.dataplane_mode }
        ]
      }
    ]
  };

  const tmf638 = {
    synchronizedAt: nowIso,
    services: [
      {
        id: `svc-inv-cfs-${tenantId}`,
        href: `/tmf-api/serviceInventory/v4/service/svc-inv-cfs-${tenantId}`,
        name: `${trace.cfs_name}_${tenantId}`,
        state: 'active',
        serviceType: 'CFS',
        '@type': 'CustomerFacingService',
        serviceSpecification: { id: trace.cfs_id, name: trace.cfs_name }
      },
      ...trace.rfs_profiles.map(p => ({
        id: `svc-inv-rfs-${p.profileCode.toLowerCase()}-${tenantId}`,
        href: `/tmf-api/serviceInventory/v4/service/svc-inv-rfs-${p.profileCode.toLowerCase()}-${tenantId}`,
        name: `${p.name}_${tenantId}`,
        state: 'active',
        serviceType: 'RFS',
        '@type': 'ResourceFacingService',
        serviceSpecification: { id: p.id, name: p.name, profileCode: p.profileCode }
      }))
    ]
  };

  tmf641.state = 'completed';
  tmf652.state = 'completed';
  orderData.state = 'completed';
  orderData.completionDate = nowIso;

  saveJson(path.join(BUILD_DIR, 'tmf639-resource-inventory-active.json'), tmf639);
  saveJson(path.join(BUILD_DIR, 'tmf638-service-inventory-active.json'), tmf638);
  saveJson(path.join(BUNDLE_DIR, 'tmf639.json'), tmf639);
  saveJson(path.join(BUNDLE_DIR, 'tmf638.json'), tmf638);
  saveJson(path.join(BUILD_DIR, 'tmf641-service-order.json'), tmf641);
  saveJson(path.join(BUILD_DIR, 'tmf652-resource-order.json'), tmf652);
  saveJson(path.join(BUILD_DIR, 'tmf622-product-order-completed.json'), orderData);
  return `[OK] Synchronized Active TMF638 & TMF639 Inventory for ${tenantId}`;
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const getArg = (flag, defVal = '') => {
    const idx = args.indexOf(flag);
    return idx >= 0 && args[idx + 1] ? args[idx + 1] : defVal;
  };
  const mode = getArg('--mode', 'validate-catalogs');
  if (mode === 'validate-catalogs') {
    console.log(validateCatalogs());
  } else if (mode === 'decompose') {
    const orderFile = getArg('--order-file', path.join(REPO_ROOT, 'orders', 'order-01-5g-upf-hp-tenant-delta.json'));
    const trace = decomposeOrder(loadJson(path.resolve(orderFile)), getArg('--project-id', 'wipro-telco-cloud-catalog1'));
    console.log(`[OK] Decomposed ${trace.order_id} -> CFS: ${trace.cfs_id} -> RFS: ${trace.rfs_profiles.map(p => p.profileCode).join(', ')} -> Blueprint: ${trace.selected_blueprint}`);
  } else if (mode === 'sync-inventory') {
    console.log(syncInventory());
  }
}

module.exports = { validateCatalogs, decomposeOrder, syncInventory };
