targetScope = 'resourceGroup'

@description('Azure region of the existing Container Apps environment.')
param location string = resourceGroup().location

param containerAppsEnvironmentName string
param containerRegistryName string
param frontendAppName string
param backendAppName string
param mcpAppName string
param ingestionWorkerAppName string
param frontendImage string
param backendImage string
param mcpImage string
param ingestionWorkerImage string

@description('Enable internet-reachable ingress for the frontend. The backend and MCP stay internal.')
param enablePublicFrontend bool = true

@description('The worker is staged at zero replicas until its required secrets are configured.')
param ingestionWorkerMinReplicas int = 0

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2026-07-01' existing = {
  name: containerAppsEnvironmentName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2026-11-01' existing = {
  name: containerRegistryName
}

resource acrPullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'radia-ai-acr-pull'
}

resource backendApp 'Microsoft.App/containerApps@2026-07-01' = {
  name: backendAppName
  location: location
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: false
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
    }
    template: {
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
      containers: [
        {
          name: 'backend'
          image: backendImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'ENVIRONMENT', value: 'production' }
            { name: 'DEBUG', value: 'false' }
            { name: 'LOG_LEVEL', value: 'INFO' }
            { name: 'API_PREFIX', value: '/api/v1' }
            { name: 'MCP_ENABLED', value: 'true' }
            { name: 'MCP_SERVER_URL', value: 'http://${mcpApp.properties.configuration.ingress.fqdn}/mcp' }
            { name: 'MCP_CONNECT_TIMEOUT_SECONDS', value: '30' }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/api/v1/health/live'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 24
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/v1/health/live'
                port: 8000
                scheme: 'HTTP'
              }
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
          ]
        }
      ]
    }
  }
}

resource mcpApp 'Microsoft.App/containerApps@2026-07-01' = {
  name: mcpAppName
  location: location
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: false
        targetPort: 8081
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
    }
    template: {
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
      containers: [
        {
          name: 'mcp-radia'
          image: mcpImage
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
          ]
          probes: [
            {
              type: 'Startup'
              tcpSocket: {
                port: 8081
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 24
            }
            {
              type: 'Liveness'
              tcpSocket: {
                port: 8081
              }
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
          ]
        }
      ]
    }
  }
}

resource frontendApp 'Microsoft.App/containerApps@2026-07-01' = {
  name: frontendAppName
  location: location
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: enablePublicFrontend
        targetPort: 8080
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
    }
    template: {
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
      containers: [
        {
          name: 'frontend'
          image: frontendImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'BACKEND_URL', value: 'http://${backendApp.properties.configuration.ingress.fqdn}' }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/'
                port: 8080
                scheme: 'HTTP'
              }
              initialDelaySeconds: 3
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 12
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/'
                port: 8080
                scheme: 'HTTP'
              }
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
          ]
        }
      ]
    }
  }
}

resource ingestionWorkerApp 'Microsoft.App/containerApps@2026-07-01' = {
  name: ingestionWorkerAppName
  location: location
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
    }
    template: {
      scale: {
        minReplicas: ingestionWorkerMinReplicas
        maxReplicas: 1
      }
      containers: [
        {
          name: 'ingestion-worker'
          image: ingestionWorkerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
            { name: 'AzureWebJobsScriptRoot', value: '/home/site/wwwroot' }
            { name: 'AzureFunctionsJobHost__Logging__Console__IsEnabled', value: 'true' }
            { name: 'ENVIRONMENT', value: 'production' }
            { name: 'LOG_LEVEL', value: 'INFO' }
          ]
          probes: [
            {
              type: 'Startup'
              tcpSocket: {
                port: 80
              }
              initialDelaySeconds: 10
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 24
            }
          ]
        }
      ]
    }
  }
}

output frontendContainerAppId string = frontendApp.id
output frontendFqdn string = frontendApp.properties.configuration.ingress.fqdn
output backendContainerAppId string = backendApp.id
output backendFqdn string = backendApp.properties.configuration.ingress.fqdn
output mcpContainerAppId string = mcpApp.id
output mcpFqdn string = mcpApp.properties.configuration.ingress.fqdn
output ingestionWorkerContainerAppId string = ingestionWorkerApp.id
