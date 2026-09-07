targetScope = 'resourceGroup'

@description('Azure region for all production resources.')
param location string = resourceGroup().location

@description('GitHub OIDC subject prefix reported by the repository settings API.')
param githubSubjectPrefix string

@description('GitHub Environment that protects production deployment.')
param githubEnvironment string = 'production'

@description('Resource name prefix.')
param prefix string = 'flash-trips-prod'

var stableSuffix = take(uniqueString(subscription().id, resourceGroup().id), 8)
var compactPrefix = 'flashtripsprod'
var acrName = '${compactPrefix}${stableSuffix}'
var keyVaultName = 'ft-prod-${stableSuffix}'
var apiAppName = '${prefix}-api'
var webAppName = '${prefix}-web'
var containerAppsEnvironmentName = '${prefix}-cae'
var logAnalyticsName = '${prefix}-logs'
var applicationInsightsName = '${prefix}-insights'
var apiIdentityName = '${prefix}-api-runtime'
var webIdentityName = '${prefix}-web-runtime'
var releaseIdentityName = '${prefix}-github-release'
var deployIdentityName = '${prefix}-github-deploy'
var placeholderImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

var acrPullRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)
var acrPushRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '8311e382-0749-4cb8-b61a-304f252e45ec'
)
var readerRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'acdd72a7-3385-48ef-bd42-f606fba81ae7'
)
var containerAppsContributorRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '358470bc-b998-42bd-ab17-a7e34c199c0f'
)
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

var tags = {
  application: 'flash-trips'
  environment: 'production'
  managedBy: 'bicep'
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    IngestionMode: 'LogAnalytics'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    enableSoftDelete: true
    publicNetworkAccess: 'Enabled'
    softDeleteRetentionInDays: 90
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: apiIdentityName
  location: location
  tags: tags
}

resource webIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: webIdentityName
  location: location
  tags: tags
}

resource releaseIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: releaseIdentityName
  location: location
  tags: tags
}

resource deployIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: deployIdentityName
  location: location
  tags: tags
}

resource releaseFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: releaseIdentity
  name: 'github-main'
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: 'https://token.actions.githubusercontent.com'
    subject: '${githubSubjectPrefix}:ref:refs/heads/main'
  }
}

resource deployFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: deployIdentity
  name: 'github-production'
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: 'https://token.actions.githubusercontent.com'
    subject: '${githubSubjectPrefix}:environment:${githubEnvironment}'
  }
}

resource releaseAcrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, releaseIdentity.id, acrPushRoleDefinitionId)
  scope: registry
  properties: {
    principalId: releaseIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPushRoleDefinitionId
  }
}

resource releaseAcrReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, releaseIdentity.id, readerRoleDefinitionId)
  scope: registry
  properties: {
    principalId: releaseIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: readerRoleDefinitionId
  }
}

resource apiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, apiIdentity.id, acrPullRoleDefinitionId)
  scope: registry
  properties: {
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource webAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, webIdentity.id, acrPullRoleDefinitionId)
  scope: registry
  properties: {
    principalId: webIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource apiKeyVaultSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, apiIdentity.id, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource deployContainerApps 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, deployIdentity.id, containerAppsContributorRoleDefinitionId)
  properties: {
    principalId: deployIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: containerAppsContributorRoleDefinitionId
  }
}

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${apiIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        allowInsecure: false
        external: false
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          identity: apiIdentity.id
          server: registry.properties.loginServer
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: placeholderImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        maxReplicas: 1
        minReplicas: 0
      }
    }
  }
  dependsOn: [
    apiAcrPull
  ]
}

resource webApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: webAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${webIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        allowInsecure: false
        external: true
        targetPort: 3000
        transport: 'auto'
      }
      registries: [
        {
          identity: webIdentity.id
          server: registry.properties.loginServer
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: placeholderImage
          env: [
            {
              name: 'FLASH_TRIPS_API_BASE_URL'
              value: 'https://${apiApp.properties.configuration.ingress.fqdn}'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        maxReplicas: 1
        minReplicas: 0
      }
    }
  }
  dependsOn: [
    webAcrPull
  ]
}

output acrName string = registry.name
output apiAppName string = apiApp.name
output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output applicationInsightsName string = applicationInsights.name
output deployClientId string = deployIdentity.properties.clientId
output keyVaultName string = keyVault.name
output releaseClientId string = releaseIdentity.properties.clientId
output webAppName string = webApp.name
output webFqdn string = webApp.properties.configuration.ingress.fqdn
