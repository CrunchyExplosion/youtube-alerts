# Deploying youtube-alerts to Azure Functions

This guide deploys `youtube-alerts` as an Azure Functions timer app. The
function checks a YouTube channel every five minutes and sends an email when a
new public video is found.

The deployment uses an Azure Functions Consumption plan and the Function App's
storage account for both Functions runtime data and alert state. The local
`.yta-state.json` file is not used in Azure.

## What you will create

- A resource group
- A general-purpose Storage Account
- A Linux Azure Function App on the Consumption plan
- One timer-triggered function named `ScanTimer`
- An Azure Table named `ytastate`, created automatically on the first run

The repository already contains the Azure entry point in `function_app.py`,
the Functions host configuration in `host.json`, and the Azure Table state
store in `src/youtubealerts/table_state.py`.

## Prerequisites

Install and sign in to the following tools:

- Python 3.11
- Azure CLI: <https://learn.microsoft.com/cli/azure/install-azure-cli>
- Azure Functions Core Tools v4:
  `npm install -g azure-functions-core-tools@4 --unsafe-perm true`

Then sign in:

```powershell
az login
```

Use a unique name for the Function App and Storage Account. Azure resource
names are shared globally and may already be taken.

## 1. Create Azure resources

Set deployment variables in PowerShell:

```powershell
$RESOURCE_GROUP = "rg-youtube-alerts"
$LOCATION = "eastus"
$STORAGE = "stytalerts$(Get-Random -Maximum 99999)"
$FUNCTION_APP = "func-youtube-alerts$(Get-Random -Maximum 99999)"
```

Create the resource group and storage account:

```powershell
az group create --name $RESOURCE_GROUP --location $LOCATION

az storage account create `
  --name $STORAGE `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard_LRS
```

Create the Function App:

```powershell
az functionapp create `
  --resource-group $RESOURCE_GROUP `
  --name $FUNCTION_APP `
  --storage-account $STORAGE `
  --consumption-plan-location $LOCATION `
  --runtime python `
  --runtime-version 3.11 `
  --functions-version 4 `
  --os-type Linux
```

The `--consumption-plan-location` option creates a pay-per-execution hosting
plan. Do not add `--plan` unless you intentionally want a separately managed
App Service plan.

## 2. Configure application settings

The Function App reads the watched channel and SMTP settings from application
settings. Replace the example values with your own values:

```powershell
az functionapp config appsettings set `
  --resource-group $RESOURCE_GROUP `
  --name $FUNCTION_APP `
  --settings `
    YTA_CHANNEL_URL="@MKBHD" `
    YTA_SMTP_HOST="smtp.gmail.com" `
    YTA_SMTP_PORT="587" `
    YTA_SMTP_USERNAME="your-account@gmail.com" `
    YTA_SMTP_PASSWORD="your-gmail-app-password" `
    YTA_ALERT_FROM="your-account@gmail.com" `
    YTA_ALERT_TO="your-alert-address@example.com"
```

For Gmail, use an App Password rather than your normal account password.
Never commit credentials or put them in this document. For a production
deployment, store the password in Azure Key Vault and reference it from the
Function App configuration.

`YTA_CHANNEL_URL` accepts the same formats as the local CLI, including a
handle, channel ID, or full channel URL.

## 3. Deploy the application

Run this command from the repository root, where `function_app.py` is located:

```powershell
func azure functionapp publish $FUNCTION_APP
```

The deployment includes `requirements.txt`, which installs the Azure Functions
runtime package, Azure Tables SDK, and this `src/`-layout project.

After deployment, open the Function App in the Azure portal and select
**Functions** to confirm that `ScanTimer` is present. The first successful run
creates the `ytastate` table and records the current video as a baseline, so it
does not send an alert immediately after the first deployment.

## 4. Enable or disable scanning

To pause only the timer without deleting the app, set the built-in disabled
setting:

```powershell
# Disable scanning
az functionapp config appsettings set `
  --resource-group $RESOURCE_GROUP `
  --name $FUNCTION_APP `
  --settings "AzureWebJobs.ScanTimer.Disabled=true"

# Enable scanning again
az functionapp config appsettings set `
  --resource-group $RESOURCE_GROUP `
  --name $FUNCTION_APP `
  --settings "AzureWebJobs.ScanTimer.Disabled=false"
```

The same setting is available in the portal under **Function App > Functions >
ScanTimer > Disable**. Disabling the timer prevents function executions, but
the storage account and other enabled services can still incur charges.

## 5. Change the watched channel

Change `YTA_CHANNEL_URL` in **Function App > Configuration > Application
settings**, save the change, and wait for the next timer run. The change does
not require a code deployment.

```powershell
az functionapp config appsettings set `
  --resource-group $RESOURCE_GROUP `
  --name $FUNCTION_APP `
  --settings "YTA_CHANNEL_URL=@SomeOtherChannel"
```

State is stored per normalized channel URL, so changing channels creates a new
baseline and does not notify for the channel's existing latest video.

## Cost considerations

Consumption pricing depends on region, execution duration, storage usage, and
whether optional monitoring is enabled. This workload is small, but Azure
pricing and free grants can change. Check the current estimate for your
subscription and region before deploying:

<https://azure.microsoft.com/pricing/details/functions/>

The storage account is required by the Functions runtime and remains billable
even when the timer is disabled. Application Insights is optional; enabling it
may add ingestion charges.

## Remove the deployment

To delete the resources created by this guide:

```powershell
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

This removes the Function App and storage account in the resource group.
