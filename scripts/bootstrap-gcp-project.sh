#!/usr/bin/env bash
# ==============================================================================
# Wipro Telco Cloud Catalog — Parameterized GCP Project & GitHub OIDC Bootstrap
# ==============================================================================
# Works seamlessly in TWO modes:
#   Mode A (Default): Authorize 'wipro-gcp-ashu/wipro-telco-cloud-catalog-gcp'
#                     against existing consolidated project 'wipro-telco-cloud-catalog1'
#   Mode B (Fresh):   Bootstrap any brand-new GCP project from scratch
#                     (APIs + GCS State Bucket + Keyless GitHub OIDC WIF Pool)
# ==============================================================================
set -euo pipefail

PROJECT_ID="${1:-wipro-telco-cloud-catalog1}"
GITHUB_REPO="${2:-wipro-gcp-ashu/wipro-telco-cloud-catalog-gcp}"
REGION="${3:-us-central1}"
CLUSTER_NAME="${4:-oda-canvas-mt-gke}"
TF_STATE_BUCKET="${PROJECT_ID}-tfstate"
POOL_NAME="github-actions-pool"
PROVIDER_NAME="github-oidc-provider"
SA_NAME="github-oda-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=================================================================="
echo " Bootstrapping GCP Project: ${PROJECT_ID}"
echo " GitHub Repository:         ${GITHUB_REPO}"
echo " Region / GKE Cluster:      ${REGION} / ${CLUSTER_NAME}"
echo "=================================================================="

gcloud services enable \
  compute.googleapis.com \
  container.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project="${PROJECT_ID}" --quiet

if ! gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access --quiet
fi

if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="GitHub Actions Telco Catalog Deployer" \
    --project="${PROJECT_ID}" --quiet
fi

for ROLE in \
  "roles/compute.networkAdmin" \
  "roles/compute.securityAdmin" \
  "roles/compute.instanceAdmin.v1" \
  "roles/container.admin" \
  "roles/iam.serviceAccountAdmin" \
  "roles/iam.serviceAccountUser" \
  "roles/resourcemanager.projectIamAdmin" \
  "roles/secretmanager.admin" \
  "roles/storage.admin" \
  "roles/run.admin" \
  "roles/artifactregistry.admin"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None --quiet >/dev/null
done

PROJECT_NUM=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")

if ! gcloud iam workload-identity-pools describe "${POOL_NAME}" --location="global" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "${POOL_NAME}" \
    --location="global" \
    --display-name="GitHub Actions Pool" \
    --project="${PROJECT_ID}" --quiet
fi

if ! gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" \
  --workload-identity-pool="${POOL_NAME}" --location="global" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_NAME}" \
    --workload-identity-pool="${POOL_NAME}" \
    --location="global" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}'" \
    --project="${PROJECT_ID}" --quiet
fi

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}" \
  --quiet >/dev/null

WIF_PROVIDER="projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"

echo ""
echo "✅ Bootstrap Complete! Configure GitHub Repository Variables with:"
echo "  gh variable set GCP_PROJECT_ID      --repo ${GITHUB_REPO} --body \"${PROJECT_ID}\""
echo "  gh variable set GCP_REGION          --repo ${GITHUB_REPO} --body \"${REGION}\""
echo "  gh variable set GKE_CLUSTER_NAME    --repo ${GITHUB_REPO} --body \"${CLUSTER_NAME}\""
echo "  gh variable set TF_STATE_BUCKET     --repo ${GITHUB_REPO} --body \"${TF_STATE_BUCKET}\""
echo "  gh variable set WIF_PROVIDER        --repo ${GITHUB_REPO} --body \"${WIF_PROVIDER}\""
echo "  gh variable set WIF_SERVICE_ACCOUNT --repo ${GITHUB_REPO} --body \"${SA_EMAIL}\""
