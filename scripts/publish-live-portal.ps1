param(
  [string]$ProjectId = "wipro-telco-cloud-catalog1",
  [string]$Region = "us-central1",
  [string]$ServiceName = "tmf-consolidated-dashboard"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PortalHtml = Join-Path $RepoRoot "docs\index.html"
$TfStateBucket = "$ProjectId-tfstate"
$Tag = Get-Date -Format "yyyyMMdd-HHmmss"

Write-Host "1/2 Uploading docs/index.html to gs://$TfStateBucket/dashboard/..." -ForegroundColor Cyan
gcloud storage cp $PortalHtml "gs://$TfStateBucket/dashboard/index.html" `
  --project=$ProjectId `
  --cache-control="no-cache,max-age=0" `
  --quiet

gcloud storage cp $PortalHtml "gs://$TfStateBucket/dashboard/TMF_Consolidated_Deployment_Dashboard.html" `
  --project=$ProjectId `
  --cache-control="no-cache,max-age=0" `
  --quiet

Write-Host "2/2 Rolling Cloud Run service $ServiceName ($Region)..." -ForegroundColor Cyan
gcloud run services update $ServiceName `
  --region=$Region `
  --project=$ProjectId `
  --update-env-vars="DASHBOARD_VERSION=wipro-telco-catalog-v13-$Tag" `
  --quiet

$LiveUrl = gcloud run services describe $ServiceName --region=$Region --project=$ProjectId --format="value(status.url)" --quiet
Write-Host "`nLIVE PORTAL UPDATED: $LiveUrl" -ForegroundColor Green
