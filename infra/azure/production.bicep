targetScope = 'subscription'

@description('Azure region for the production resource group.')
param location string = 'westeurope'

@description('Production resource group name.')
param resourceGroupName string = 'flash-trips-prod-rg'

@description('GitHub OIDC subject prefix reported by the repository settings API.')
param githubSubjectPrefix string

@description('GitHub Environment that protects production deployment.')
param githubEnvironment string = 'production'

resource productionResourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: {
    application: 'flash-trips'
    environment: 'production'
    managedBy: 'bicep'
  }
}

module production 'main.bicep' = {
  name: 'flash-trips-production'
  scope: productionResourceGroup
  params: {
    githubEnvironment: githubEnvironment
    githubSubjectPrefix: githubSubjectPrefix
    location: location
  }
}

output acrName string = production.outputs.acrName
output apiAppName string = production.outputs.apiAppName
output apiFqdn string = production.outputs.apiFqdn
output applicationInsightsName string = production.outputs.applicationInsightsName
output deployClientId string = production.outputs.deployClientId
output keyVaultName string = production.outputs.keyVaultName
output releaseClientId string = production.outputs.releaseClientId
output resourceGroupName string = productionResourceGroup.name
output webAppName string = production.outputs.webAppName
output webFqdn string = production.outputs.webFqdn
