@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Name prefix used for every resource created by this template.')
param namePrefix string = 'radia-mcp'

@description('Container image for mcp-radia, e.g. myregistry.azurecr.io/mcp-radia:latest.')
param containerImage string

@description('Login server of the container registry hosting containerImage (empty if a public image).')
param containerRegistryServer string = ''

@description('User-assigned managed identity resource ID granted AcrPull on containerRegistryServer, when set.')
param acrPullIdentityId string = ''

@description('Shared bearer token the backend must send on every MCP request. Store the real value in Key Vault / a pipeline secret, never in source control.')
@secure()
param mcpServiceToken string

@description('Jama Connect instance root URL, e.g. https://yourorg.jamacloud.com. Leave empty to deploy with Jama unconfigured.')
param jamaBaseUrl string = ''

@description('Existing subnet resource ID to inject the Container Apps environment into, for VNet-integrated internal ingress. Leave empty to let Container Apps manage its own (still internal-only, but not peerable from outside Azure).')
param infrastructureSubnetId string = ''

@description('Whether the MCP endpoint is reachable only from inside the Container Apps environment network. Keep true outside of a throwaway dev deployment: this server must never be reachable from the public internet.')
param ingressInternalOnly bool = true

@description('Minimum number of replicas. 1 keeps a warm instance so chat requests do not pay a cold-start MCP handshake.')
param minReplicas int = 1

@description('Maximum number of replicas.')
param maxReplicas int = 3

var logAnalyticsName = '${namePrefix}-logs'
var environmentName = '${namePrefix}-env'
var containerAppName = '${namePrefix}-app'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: empty(infrastructureSubnetId) ? null : {
      infrastructureSubnetId: infrastructureSubnetId
      internal: true
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  identity: empty(acrPullIdentityId)
    ? {
        type: 'None'
      }
    : {
        type: 'UserAssigned'
        userAssignedIdentities: {
          '${acrPullIdentityId}': {}
        }
      }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      // Internal-only: reachable from other apps in this Container Apps
      // environment (and, when infrastructureSubnetId is set, from anything
      // peered into that VNet - e.g. the RadiaAI backend, if it is also
      // VNet-integrated). Never flip this without re-reading
      // docs/architecture.md's security section: this is a read-only
      // integration layer for engineering data, not a public API.
      ingress: {
        external: !ingressInternalOnly
        targetPort: 8081
        transport: 'http'
        allowInsecure: false
      }
      registries: empty(containerRegistryServer)
        ? []
        : [
            {
              server: containerRegistryServer
              identity: acrPullIdentityId
            }
          ]
      secrets: [
        {
          name: 'mcp-service-token'
          value: mcpServiceToken
        }
      ]
    }
    template: {
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
      containers: [
        {
          name: 'mcp-radia'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'MCP_RADIA_ENVIRONMENT', value: 'production' }
            { name: 'MCP_RADIA_LOG_LEVEL', value: 'INFO' }
            { name: 'MCP_RADIA_HOST', value: '0.0.0.0' }
            { name: 'MCP_RADIA_PORT', value: '8081' }
            { name: 'MCP_RADIA_HTTP_PATH', value: '/mcp' }
            { name: 'MCP_RADIA_SERVICE_TOKEN', secretRef: 'mcp-service-token' }
            // No Jama credentials: every Jama call runs as the signed-in user,
            // whose linked OAuth client the backend forwards per request.
            { name: 'JAMA_BASE_URL', value: jamaBaseUrl }
          ]
          probes: [
            {
              // The MCP endpoint itself requires the bearer token and expects
              // JSON-RPC framing, so it cannot double as a health probe. This
              // only verifies the process is accepting TCP connections.
              type: 'Startup'
              tcpSocket: {
                port: 8081
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              failureThreshold: 10
            }
          ]
        }
      ]
    }
  }
}

@description('Resource ID of the deployed Container App, for VNet/role-assignment wiring.')
output containerAppId string = containerApp.id

@description('Internal FQDN the backend should use as MCP_SERVER_URL (scheme + /mcp path still required).')
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
