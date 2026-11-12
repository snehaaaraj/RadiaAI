targetScope = 'resourceGroup'

@description('Azure region for the registry-pull managed identity.')
param location string = resourceGroup().location

param containerRegistryName string

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2026-11-01' existing = {
  name: containerRegistryName
}

// Preauthorize ACR access before creating app revisions, avoiding first-pull RBAC races.
resource acrPullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'radia-ai-acr-pull'
  location: location
}

var acrPullRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, acrPullIdentity.id, acrPullRoleDefinitionId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: acrPullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output acrPullIdentityId string = acrPullIdentity.id
