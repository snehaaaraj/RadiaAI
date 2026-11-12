targetScope = 'resourceGroup'

@description('Azure region for the new shared Container Apps infrastructure.')
param location string = resourceGroup().location

@description('Name of the new Consumption Container Apps environment.')
param containerAppsEnvironmentName string

@description('Name of the new Log Analytics workspace.')
param logAnalyticsWorkspaceName string

@description('Globally unique name of the new Azure Container Registry.')
param containerRegistryName string

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2026-03-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    environmentMode: 'ConsumptionOnly'
    publicNetworkAccess: 'Enabled'
    peerAuthentication: {
      mtls: {
        enabled: false
      }
    }
    peerTrafficConfiguration: {
      encryption: {
        enabled: false
      }
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2026-11-01' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    dataEndpointEnabled: false
    encryption: {
      status: 'disabled'
    }
    endpointProtocol: 'IPv4'
    networkRuleBypassAllowedForTasks: false
    regionalEndpoints: 'Disabled'
    roleAssignmentMode: 'LegacyRegistryPermissions'
  }
}

output containerAppsEnvironmentId string = containerAppsEnvironment.id
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
