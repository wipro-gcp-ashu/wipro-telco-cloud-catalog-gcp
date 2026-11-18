param(
  [string]$ProjectId = "wipro-telco-cloud-catalog1",
  [string]$GitHubRepo = "wipro-gcp-ashu/wipro-telco-cloud-catalog-gcp",
  [string]$Region = "us-central1",
  [string]$ClusterName = "oda-canvas-mt-gke"
)

$ErrorActionPreference = "Stop"
$TfStateBucket = "$ProjectId-tfstate"
$PoolName = "github-actions-pool"
$ProviderName = "github-oidc-provider"
$SaName = "github-oda-deployer"
$SaEmail = "$SaName@$ProjectId.iam.gserviceaccount.com"

Write-Host "Bootstrapping GCP Project [$ProjectId] for GitHub Repo [$GitHubRepo]..." -ForegroundColor Cyan

$ProjectNum = gcloud projects describe $ProjectId --format="value(projectNumber)" --quiet

gcloud iam service-accounts add-iam-policy-binding $SaEmail `
  --project=$ProjectId `
  --role="roles/iam.workloadIdentityUser" `
  --member="principalSet://iam.googleapis.com/projects/$ProjectNum/locations/global/workloadIdentityPools/$PoolName/attribute.repository/$GitHubRepo" `
  --quiet | Out-Null

$WifProvider = "projects/$ProjectNum/locations/global/workloadIdentityPools/$PoolName/providers/$ProviderName"

Write-Host "`nGitHub Repository Variables for $GitHubRepo :" -ForegroundColor Green
Write-Host "  GCP_PROJECT_ID      = $ProjectId"
Write-Host "  GCP_REGION          = $Region"
Write-Host "  GKE_CLUSTER_NAME    = $ClusterName"
Write-Host "  TF_STATE_BUCKET     = $TfStateBucket"
Write-Host "  WIF_PROVIDER        = $WifProvider"
Write-Host "  WIF_SERVICE_ACCOUNT = $SaEmail"
