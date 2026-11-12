# Deploying RadiaAI to Azure Container Apps

Step-by-step runbook for the Vercel -> Azure migration. **You run every command**; nothing
here is executed for you. Keep Vercel running until section 10 (cut-over) is done.

Target (decided in the Phase 1 assessment): **Azure Container Apps, VNet-injected**, four
independently deployable apps:

| App | Image source | Ingress | Notes |
|-----|--------------|---------|-------|
| `ca-frontend` | `frontend/Dockerfile` (nginx, port 8080) | external | static SPA |
| `ca-backend` | `backend/Dockerfile` (uvicorn, port 8000) | external | FastAPI API |
| `ca-mcp-radia` | `mcp-radia/Dockerfile` (port 8081) | **internal** | only the backend can reach it |
| `ca-worker` | `backend/Dockerfile.worker` | none | queue-triggered ingestion worker |

> **Why the first deployment is "interim public".** A Container Apps environment is either
> *external* or *internal*, and that cannot be changed after it is created. An internal
> environment is only reachable from inside the VNet, and the VNet is not yet connected to
> the Boulder/Seattle/Texas networks (that needs IT). So you first deploy an **external**
> environment locked to the offices' public IPs with an ingress IP allow-list plus Entra
> sign-in, then rebuild the environment as **internal** once IT connects the network
> (section 11). The VNet, registry, Key Vault, identities and images are reused.

## 0. Prerequisites

- Azure CLI 2.89+ signed in as an **Owner** of the subscription (`az login`).
- Container Apps CLI extension: `az extension add --name containerapp --upgrade`
- Real values for the settings in section 5. Copy them from the Vercel project settings
  (Vercel -> Project -> Settings -> Environment Variables). **Never paste them into chat,
  commits or screenshots.**
- The public IP address(es) of the Boulder, Seattle and Texas offices/VPN egress (ask IT).
  Find your own with `curl https://api.ipify.org` while on the VPN.

Run all commands in PowerShell. Set these variables once per terminal session:

```powershell
$SUB      = "88c26b31-7797-4a1f-9c2c-b019dafb3401"
$RG       = "rg-radiaai-prod"
$LOC      = "centralus"                 # closest to Search/Storage and to all three offices
$VNET     = "vnet-radiaai"
$SUBNET   = "snet-aca"
$ACR      = "radiaaiprodacr"            # must be globally unique, lowercase letters/numbers
$KV       = "kv-radiaai-prod"           # must be globally unique
$LAW      = "log-radiaai"
$IDENT    = "id-radiaai-apps"
$ENVNAME  = "cae-radiaai"
```

## 1. Register providers and create the resource group

Explanation: `Microsoft.Network` is not registered yet; the VNet needs it. Registration is
free and creates nothing.

```powershell
az account set --subscription $SUB
az provider register --namespace Microsoft.Network --wait
az provider register --namespace Microsoft.App --wait
az provider show -n Microsoft.Network --query registrationState -o tsv   # expect: Registered

az group create --name $RG --location $LOC
```

## 2. Logging, network, identity

```powershell
# Log Analytics workspace (container logs go here)
az monitor log-analytics workspace create -g $RG -n $LAW -l $LOC

# VNet + a subnet dedicated to Container Apps (/26 leaves room to scale; minimum is /27)
az network vnet create -g $RG -n $VNET -l $LOC `
  --address-prefixes 10.20.0.0/16 `
  --subnet-name $SUBNET --subnet-prefixes 10.20.0.0/26
az network vnet subnet update -g $RG --vnet-name $VNET -n $SUBNET `
  --delegations Microsoft.App/environments

# One managed identity shared by all apps (pulls images, reads Key Vault secrets)
az identity create -g $RG -n $IDENT -l $LOC
$IDENT_ID  = az identity show -g $RG -n $IDENT --query id -o tsv
$IDENT_PID = az identity show -g $RG -n $IDENT --query principalId -o tsv
```

> The `10.20.0.0/16` range is a placeholder. IT may require a different range that does not
> overlap the corporate network (see section 11). If so, delete and recreate this VNet before
> creating the environment.

## 3. Registry and Key Vault

```powershell
# Registry (Basic is enough now; upgrade to Premium in section 11 for private endpoints)
az acr create -g $RG -n $ACR --sku Basic -l $LOC
$ACR_ID = az acr show -g $RG -n $ACR --query id -o tsv
az role assignment create --assignee-object-id $IDENT_PID --assignee-principal-type ServicePrincipal `
  --role AcrPull --scope $ACR_ID

# Key Vault using Azure RBAC
az keyvault create -g $RG -n $KV -l $LOC --enable-rbac-authorization true
$KV_ID = az keyvault show -g $RG -n $KV --query id -o tsv
az role assignment create --assignee-object-id $IDENT_PID --assignee-principal-type ServicePrincipal `
  --role "Key Vault Secrets User" --scope $KV_ID

# Let *you* write secrets
$ME = az ad signed-in-user show --query id -o tsv
az role assignment create --assignee-object-id $ME --assignee-principal-type User `
  --role "Key Vault Secrets Officer" --scope $KV_ID
```

Role assignments can take a couple of minutes to apply.

## 4. Store the secrets in Key Vault

Prompting avoids leaving values in your shell history. Repeat for each secret in this table:

| Key Vault secret name | Backend / worker setting it feeds |
|-----------------------|-----------------------------------|
| `azure-openai-api-key` | `AZURE_OPENAI_API_KEY` |
| `azure-search-api-key` | `AZURE_SEARCH_API_KEY` |
| `azure-blob-connection-string` | `AZURE_BLOB_CONNECTION_STRING`, worker `AzureWebJobsStorage` |
| `sharepoint-client-secret` | `SHAREPOINT_CLIENT_SECRET` |
| `entra-client-secret` | `ENTRA_CLIENT_SECRET` (only if you use it today) |
| `jama-credential-encryption-key` | `JAMA_CREDENTIAL_ENCRYPTION_KEY` - **reuse the Vercel value**, otherwise users' linked Jama accounts stop decrypting |
| `mcp-service-token` | backend `MCP_SERVICE_TOKEN` **and** mcp-radia `MCP_RADIA_SERVICE_TOKEN` (same value) |
| `atlassian-api-token` | mcp-radia `ATLASSIAN_API_TOKEN` (only if used) |

```powershell
function Set-KvSecret($name) {
  $v = Read-Host "Value for $name" -AsSecureString
  $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($v))
  az keyvault secret set --vault-name $KV --name $name --value $plain --output none
}
Set-KvSecret "azure-openai-api-key"
Set-KvSecret "azure-search-api-key"
Set-KvSecret "azure-blob-connection-string"
Set-KvSecret "sharepoint-client-secret"
Set-KvSecret "jama-credential-encryption-key"

# New MCP token (do not reuse the Vercel one)
$tok = -join ((48..57 + 97..102) | Get-Random -Count 64 | ForEach-Object {[char]$_})
az keyvault secret set --vault-name $KV --name mcp-service-token --value $tok --output none
Remove-Variable tok
```

## 5. Build the images in Azure (no local Docker needed)

`az acr build` builds in Azure (amd64) and pushes straight to the registry. Run from the
repository root. The frontend needs its public settings as build arguments because Vite
bakes them in at build time - so it is built in section 8d, once the backend URL is known.

The frontend image is built with the **repository root** as context (`vite.config.ts` reads
`backend/app/VERSION`). The root `.dockerignore` limits what is uploaded to `frontend/` and
that one file, so no `.env` file is ever sent.

```powershell
$TAG = (git rev-parse --short HEAD)
az acr build -r $ACR -t "radia-backend:$TAG"  -f backend/Dockerfile        backend
az acr build -r $ACR -t "radia-worker:$TAG"   -f backend/Dockerfile.worker backend
az acr build -r $ACR -t "radia-mcp:$TAG"      -f mcp-radia/Dockerfile      mcp-radia
$LOGIN = az acr show -n $ACR --query loginServer -o tsv
```

## 6. Create the Container Apps environment (interim: external, in your VNet)

```powershell
$LAW_ID  = az monitor log-analytics workspace show -g $RG -n $LAW --query customerId -o tsv
$LAW_KEY = az monitor log-analytics workspace get-shared-keys -g $RG -n $LAW --query primarySharedKey -o tsv
$SUBNET_ID = az network vnet subnet show -g $RG --vnet-name $VNET -n $SUBNET --query id -o tsv

az containerapp env create -g $RG -n $ENVNAME -l $LOC `
  --infrastructure-subnet-resource-id $SUBNET_ID `
  --logs-workspace-id $LAW_ID --logs-workspace-key $LAW_KEY `
  --enable-workload-profiles true

$DOMAIN = az containerapp env show -g $RG -n $ENVNAME --query properties.defaultDomain -o tsv
$FRONT_URL = "https://ca-frontend.$DOMAIN"
$BACK_URL  = "https://ca-backend.$DOMAIN"
"$FRONT_URL`n$BACK_URL"
```

The app URLs are predictable, so you can register them with Entra and use them in settings
before the apps exist.

## 7. Entra ID: allow the new URL to sign in

In the Azure portal -> Microsoft Entra ID -> App registrations -> the **SPA** registration
(`Radia AI Web`, or whatever it is called) -> Authentication -> *Single-page application*
-> **add** the `$FRONT_URL` value as a redirect URI. Keep the Vercel URIs until cut-over.
No other Entra change is needed (the API registration and roles are unchanged).

## 8. Deploy the apps

Secrets reference Key Vault through the managed identity (`keyvaultref`). The vault URI is:

```powershell
$KV_URI = "https://$KV.vault.azure.net/secrets"
$TAG = (git rev-parse --short HEAD)   # same tag as section 5
```

### 8a. mcp-radia (internal, a single replica)

One replica is required: mcp-radia runs in stateful mode and the backend client does not
recover if a later request lands on a different replica.

```powershell
az containerapp create -g $RG -n ca-mcp-radia --environment $ENVNAME `
  --image "$LOGIN/radia-mcp:$TAG" `
  --registry-server $LOGIN --registry-identity $IDENT_ID `
  --user-assigned $IDENT_ID `
  --ingress internal --target-port 8081 --transport http `
  --min-replicas 1 --max-replicas 1 --cpu 0.5 --memory 1Gi `
  --secrets "mcp-token=keyvaultref:$KV_URI/mcp-service-token,identityref:$IDENT_ID" `
  --env-vars MCP_RADIA_ENVIRONMENT=production MCP_RADIA_LOG_LEVEL=INFO `
             MCP_RADIA_HOST=0.0.0.0 MCP_RADIA_PORT=8081 MCP_RADIA_HTTP_PATH=/mcp `
             MCP_RADIA_SERVICE_TOKEN=secretref:mcp-token `
             JAMA_BASE_URL=https://<yourorg>.jamacloud.com

$MCP_FQDN = az containerapp show -g $RG -n ca-mcp-radia --query properties.configuration.ingress.fqdn -o tsv
"MCP URL for the backend: https://$MCP_FQDN/mcp"
```

### 8b. Backend

Fill in the `<...>` values from your Vercel settings. Non-secret values are plain; secrets
use `secretref:`.

```powershell
az containerapp create -g $RG -n ca-backend --environment $ENVNAME `
  --image "$LOGIN/radia-backend:$TAG" `
  --registry-server $LOGIN --registry-identity $IDENT_ID `
  --user-assigned $IDENT_ID `
  --ingress external --target-port 8000 --transport http `
  --min-replicas 1 --max-replicas 4 --cpu 1.0 --memory 2Gi `
  --scale-rule-name http-load --scale-rule-type http --scale-rule-http-concurrency 10 `
  --secrets "openai-key=keyvaultref:$KV_URI/azure-openai-api-key,identityref:$IDENT_ID" `
            "search-key=keyvaultref:$KV_URI/azure-search-api-key,identityref:$IDENT_ID" `
            "blob-conn=keyvaultref:$KV_URI/azure-blob-connection-string,identityref:$IDENT_ID" `
            "sp-secret=keyvaultref:$KV_URI/sharepoint-client-secret,identityref:$IDENT_ID" `
            "jama-key=keyvaultref:$KV_URI/jama-credential-encryption-key,identityref:$IDENT_ID" `
            "mcp-token=keyvaultref:$KV_URI/mcp-service-token,identityref:$IDENT_ID" `
  --env-vars ENVIRONMENT=production `
             "ALLOWED_ORIGINS=$FRONT_URL" `
             "ALLOWED_ORIGIN_REGEX=" `
             AZURE_OPENAI_ENDPOINT=<https://...openai.azure.com> AZURE_OPENAI_API_KEY=secretref:openai-key `
             AZURE_OPENAI_API_VERSION=<same as Vercel> `
             AZURE_OPENAI_CHAT_DEPLOYMENT=<...> AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<...> `
             AZURE_SEARCH_ENDPOINT=<https://radia-ai-2-0-search.search.windows.net> AZURE_SEARCH_API_KEY=secretref:search-key `
             AZURE_SEARCH_INDEX_NAME=<same as Vercel> `
             AZURE_BLOB_CONNECTION_STRING=secretref:blob-conn AZURE_BLOB_CONTAINER_NAME=<same as Vercel> `
             ENTRA_TENANT_ID=eeb96edb-0303-4889-b4d8-6050ed38f182 ENTRA_CLIENT_ID=<API app client id> `
             SHAREPOINT_TENANT_ID=<...> SHAREPOINT_CLIENT_ID=<...> SHAREPOINT_CLIENT_SECRET=secretref:sp-secret `
             SHAREPOINT_SITE_URL=<...> SHAREPOINT_WEBHOOK_ENABLED=false `
             JAMA_BASE_URL=https://<yourorg>.jamacloud.com JAMA_CREDENTIAL_ENCRYPTION_KEY=secretref:jama-key `
             MCP_ENABLED=true MCP_SERVER_URL=https://$MCP_FQDN/mcp MCP_SERVICE_TOKEN=secretref:mcp-token `
             "MCP_ALLOWED_TOOLS=jama_get_item,jama_search,jama_get_children,jama_list_projects,list_related_items"
```

Copy any other setting you use on Vercel (see `backend/.env.example` for every name). Notes:

- `ENVIRONMENT=production` makes the app **refuse to start** unless Entra is configured. That
  is intentional - it can never run unauthenticated.
- `ALLOWED_ORIGIN_REGEX=` (empty) turns off the `*.vercel.app` CORS rule.
- `ALLOWED_ORIGINS` accepts a JSON list or a plain comma-separated value. Use the plain form
  (`ALLOWED_ORIGINS=$FRONT_URL`): PowerShell strips the quotes out of a JSON value, which
  silently produces a wrong origin and blocks the browser with a CORS error.
- `SHAREPOINT_WEBHOOK_ENABLED=false`: the SharePoint "document edited" trigger is deferred;
  use the manual/queued ingest meanwhile.
- Add liveness/readiness probes in the Portal (Container App -> Containers -> Health probes):
  liveness `GET /api/v1/health/live`, readiness `GET /api/v1/health/ready`, port 8000.

### 8c. Worker (ingestion)

Uses the same storage, OpenAI, Search and SharePoint settings as the backend. Use the same
`INGESTION_QUEUE_NAME` as the backend (default `radia-ingestion`). It has no ingress and must
keep one replica running (it hosts the 2-minute recovery timer).

```powershell
az containerapp create -g $RG -n ca-worker --environment $ENVNAME `
  --image "$LOGIN/radia-worker:$TAG" `
  --registry-server $LOGIN --registry-identity $IDENT_ID `
  --user-assigned $IDENT_ID `
  --min-replicas 1 --max-replicas 1 --cpu 1.0 --memory 2Gi `
  --secrets "openai-key=keyvaultref:$KV_URI/azure-openai-api-key,identityref:$IDENT_ID" `
            "search-key=keyvaultref:$KV_URI/azure-search-api-key,identityref:$IDENT_ID" `
            "blob-conn=keyvaultref:$KV_URI/azure-blob-connection-string,identityref:$IDENT_ID" `
            "sp-secret=keyvaultref:$KV_URI/sharepoint-client-secret,identityref:$IDENT_ID" `
  --env-vars ENVIRONMENT=production `
             AzureWebJobsStorage=secretref:blob-conn `
             AZURE_BLOB_CONNECTION_STRING=secretref:blob-conn AZURE_BLOB_CONTAINER_NAME=<same as backend> `
             INGESTION_QUEUE_NAME=radia-ingestion `
             AZURE_OPENAI_ENDPOINT=<...> AZURE_OPENAI_API_KEY=secretref:openai-key `
             AZURE_OPENAI_API_VERSION=<...> AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<...> AZURE_OPENAI_CHAT_DEPLOYMENT=<...> `
             AZURE_SEARCH_ENDPOINT=<...> AZURE_SEARCH_API_KEY=secretref:search-key AZURE_SEARCH_INDEX_NAME=<...> `
             SHAREPOINT_TENANT_ID=<...> SHAREPOINT_CLIENT_ID=<...> SHAREPOINT_CLIENT_SECRET=secretref:sp-secret `
             SHAREPOINT_SITE_URL=<...>
```

> The subscription already has older Function apps (`radia-sharepoint-ingest`,
> `radia-preprocess`, `radia-index`). Do not point this worker at queues they use.

### 8d. Frontend

For the same-origin proxy configuration, build with `VITE_API_BASE_URL=/api/v1`
and set the frontend container's runtime `BACKEND_URL` to the backend's HTTPS
origin (no path or trailing slash). The nginx proxy preserves `/api/...` and
uses the backend hostname for routing and TLS verification. To accommodate
intermediate CAs, nginx permits a verification depth of three while keeping
certificate verification enabled. The backend can
then keep internal ingress in the same environment. No backend secrets belong
in the frontend image. Changing `VITE_*` settings requires rebuilding the image;
changing `BACKEND_URL` requires a new Container App revision.

The frontend build needs the SPA registration and redirect URL; the backend URL
is supplied at runtime through `BACKEND_URL`.
`VITE_*` values are public; they are not secrets. Run from the repository root; the trailing
`.` is the build context.

```powershell
az acr build -r $ACR -t "radia-frontend:$TAG" -f frontend/Dockerfile `
  --build-arg VITE_API_BASE_URL="/api/v1" `
  --build-arg VITE_ENTRA_CLIENT_ID=<SPA app client id> `
  --build-arg VITE_ENTRA_TENANT_ID=eeb96edb-0303-4889-b4d8-6050ed38f182 `
  --build-arg VITE_ENTRA_API_SCOPE="api://<API app client id>/access_as_user" `
  --build-arg VITE_ENTRA_REDIRECT_URI=$FRONT_URL `
  .

az containerapp create -g $RG -n ca-frontend --environment $ENVNAME `
  --image "$LOGIN/radia-frontend:$TAG" `
  --registry-server $LOGIN --registry-identity $IDENT_ID `
  --user-assigned $IDENT_ID `
  --ingress external --target-port 8080 --transport http `
  --min-replicas 1 --max-replicas 3 --cpu 0.25 --memory 0.5Gi `
  --env-vars "BACKEND_URL=$BACK_URL"
```

## 9. Lock access to the offices and verify end to end

### 9a. IP allow-list (interim protection)

Adding the first Allow rule makes the app reject every other address. Add one rule per
office/VPN egress range, for **both** the frontend and the backend (the browser calls the
backend directly). mcp-radia and the worker are not reachable from outside anyway.

```powershell
foreach ($app in "ca-frontend","ca-backend") {
  az containerapp ingress access-restriction set -g $RG -n $app `
    --rule-name boulder --ip-address <BOULDER_CIDR> --action Allow
  az containerapp ingress access-restriction set -g $RG -n $app `
    --rule-name seattle --ip-address <SEATTLE_CIDR> --action Allow
  az containerapp ingress access-restriction set -g $RG -n $app `
    --rule-name texas   --ip-address <TEXAS_CIDR>   --action Allow
}
az containerapp ingress access-restriction list -g $RG -n ca-backend -o table
```

Do this **before** sharing the URLs. Remember that Entra sign-in and the `Radia.User` /
`Radia.Admin` roles still protect every API call; the allow-list is an extra layer.

### 9b. Verification checklist (from an allowed address)

| # | Check | Expected |
|---|-------|----------|
| 1 | `curl -s "$BACK_URL/api/v1/health/live"` | HTTP 200 |
| 2 | `curl -s "$BACK_URL/api/v1/health/ready"` | 200, and each dependency (OpenAI, Search, Blob) healthy |
| 3 | `curl -s -o NUL -w "%{http_code}" "$BACK_URL/api/v1/auth/me"` | **401** (auth enforced) |
| 4 | Open `$FRONT_URL` in a browser | Microsoft sign-in, then the Launchpad |
| 5 | Settings -> your Jama account still shows linked | Proves the encryption key and Blob are shared with Vercel |
| 6 | Run a single-requirement review | Result < 60 s |
| 7 | Run a set review with ~10 requirements | Items complete progressively, no gateway errors |
| 8 | Chat -> turn Radia AI on -> ask about a Jama item | Answer shows the "Engineering data" chip |
| 9 | From a machine **not** on the allow-list, open `$FRONT_URL` | 403 |
| 10 | Logs: `az containerapp logs show -g $RG -n ca-backend --follow` | `application_startup`, no errors. Look for `mcp_tools_discovered` after check 8 |
| 11 | Logs of `ca-mcp-radia` / `ca-worker` | Running; worker shows the Functions host started |

If check 8 fails, confirm `MCP_SERVICE_TOKEN` (backend) and `MCP_RADIA_SERVICE_TOKEN`
(mcp-radia) resolve to the same Key Vault secret.

## 10. Cut-over from Vercel (no downtime)

1. Keep Vercel live while you test on the Azure URLs.
2. Tell users the new URL (there is no custom domain; they use `$FRONT_URL`), or give IT the
   hostname to publish internally later (section 11).
3. After a week of stable use, remove the Vercel redirect URIs from the SPA registration.
4. Pause (do not delete) the Vercel projects.

**Rollback:** the Vercel deployments are untouched, so point users back to them. To roll
back one Azure app to its previous version:

```powershell
az containerapp revision list -g $RG -n ca-backend -o table
az containerapp ingress traffic set -g $RG -n ca-backend --revision-weight <previous-revision>=100
```

(Apps default to single-revision mode, where a new deployment replaces the old one; to keep
the old revision available, switch with `az containerapp revision set-mode --mode multiple`.)

## 11. Going private (when IT connects the network)

### What to ask IT (this is the specification)

| Request | Details |
|---------|---------|
| Connectivity | Site-to-site VPN or ExpressRoute from Boulder, Seattle and Texas to the Azure VNet in **Central US** (subscription `88c26b31-...`), or peering with an existing hub VNet that already has it |
| Address space | A VNet range that does **not overlap** corporate ranges (the placeholder is `10.20.0.0/16`) and two subnets: a **/26** for Container Apps (delegated to `Microsoft.App/environments`) and a small one for private endpoints |
| DNS | A private DNS zone for the environment's default domain, linked to the VNet, with a wildcard A record pointing at the internal environment's static IP; corporate DNS forwards that zone to Azure. Or an internal hostname such as `radia.<company-domain>` |
| Certificate | An internal-CA TLS certificate for that hostname (there is no public custom domain) |
| NSG rules | Inbound 443 only from corporate ranges; outbound to Azure services, `login.microsoftonline.com`, Microsoft Graph, and Jama |
| Fixed outbound IP | Only if Jama allow-lists addresses: a NAT Gateway on the Container Apps subnet |
| Later | Private endpoints for Key Vault, Storage, Search, OpenAI and the registry |

### Switch procedure

1. Upgrade the registry for private endpoints: `az acr update -n $ACR --sku Premium`.
2. Create a **second** subnet and a new **internal** environment in it:
   `az containerapp env create ... --internal-only true` (same other flags).
3. Re-run section 8 against the new environment (the images and secrets already exist).
4. Create the private DNS zone/records for the new environment's domain; update
   `ALLOWED_ORIGINS`, the frontend build args (`VITE_API_BASE_URL`, `VITE_ENTRA_REDIRECT_URI`)
   and the Entra redirect URI to the new internal hostname.
5. Test from the VPN, then delete the old external environment and its apps.

## 12. Redeploying a single service later

Each service deploys on its own; nothing else restarts.

```powershell
$TAG = (git rev-parse --short HEAD)
az acr build -r $ACR -t "radia-backend:$TAG" -f backend/Dockerfile backend
az containerapp update -g $RG -n ca-backend --image "$LOGIN/radia-backend:$TAG"
# frontend: rebuild with the same --build-arg values as section 8d, then update ca-frontend
# mcp-radia: radia-mcp image -> ca-mcp-radia    worker: radia-worker image -> ca-worker
```

GitHub Actions workflows with OIDC (no stored Azure password) for these three deployments
are the next step once the manual deployment works.

## 13. Known limits and open items

- **240-second request limit:** a Container Apps request is cut off after 240 s. Single and
  delta reviews fit; set review issues one request per requirement from the browser. The
  OpenAI client now times out after 90 s per call (1 retry) and the browser after 230 s so
  failures are clean. Very large delta reviews score requirements sequentially, so watch their
  duration.
- **mcp-radia scaling:** keep 1 replica (stateful sessions). A client change to recover from a
  lost session would allow more.
- **SharePoint "document edited" webhook:** disabled for now. Options for later: Graph
  notifications delivered to Azure Event Hubs (no public URL needed), a WAF-protected public
  webhook path, or scheduled ingestion.
- **Network exposure:** OpenAI, Search and Storage remain publicly reachable (protected by
  keys) until private endpoints are added in section 11.
- **Cost:** about $50-130/month for the interim setup (mostly compute and logs); the private
  design adds ACR Premium, private endpoints and DNS (about $260/month overall). These are
  estimates; confirm with the Azure Pricing Calculator.
