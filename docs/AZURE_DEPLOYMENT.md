# Deploying to Azure at Minimum Cost

Target: **Azure Functions, Consumption plan, Timer Trigger** — replaces the local
`youtube-alerts --watch` loop with a scheduled cloud function. Expected cost: **$0–$1/month**
(free execution grant covers this workload; only a tiny Storage Account cost applies).
Includes a **built-in on/off toggle** and a **channel that's changeable from the
Portal** — neither requires touching code or redeploying.

## Architecture

```
Azure Function App (Consumption / Y1, Linux, Python)
  └─ Timer Trigger "ScanTimer" (e.g. every 5 min, CRON in host config)
       └─ calls scan_once() [reused from scanner.py, unchanged logic]
            ├─ fetch_latest_video()  [scraper/* — unchanged]
            ├─ state  → Azure Table Storage (replaces local .yta-state.json)
            └─ notify → same SMTP EmailNotifier (creds from App Settings, not .env)

Storage Account (required by Functions runtime + hosts the state table)
```

## Prerequisites

- Azure CLI (`az`) logged in: `az login`
- Azure Functions Core Tools v4: `npm i -g azure-functions-core-tools@4 --unsafe-perm true`
- Python 3.11 locally (match the Function App runtime version)

## Step 1 — Create the resource group and storage account

```powershell
az group create -n rg-youtube-alerts -l eastus

az storage account create `
  -n stytalerts$(Get-Random -Maximum 99999) `
  -g rg-youtube-alerts -l eastus --sku Standard_LRS
```

Note the storage account name it prints — you'll reuse it below (`$STORAGE`).

## Step 2 — Create the Function App (Consumption plan = pay-per-execution)

```powershell
az functionapp create `
  -g rg-youtube-alerts -n func-youtube-alerts$(Get-Random -Maximum 99999) `
  --storage-account $STORAGE `
  --consumption-plan-location eastus `
  --runtime python --runtime-version 3.11 `
  --functions-version 4 `
  --os-type Linux
```

`--consumption-plan-location` is what makes this serverless/pay-per-use — do
**not** use `--plan`/App Service Plan flags, that creates always-on paid compute.

## Step 3 — Adapt the code (minimal change)

Only `scanner.py`'s state I/O changes; `scraper/`, `models.py`, `exceptions.py`,
`config.py` are reused as-is. Add a new entry point instead of `cli.py`:

**`function_app.py`** (new file, project root):

```python
import os
import azure.functions as func
import logging
from youtubealerts.scanner import scan_once, EmailNotifier
from table_state import load_state, save_state  # new helper, see below

app = func.FunctionApp()

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False)
def ScanTimer(timer: func.TimerRequest) -> None:
    channel_url = os.environ["YTA_CHANNEL_URL"]  # read fresh on every run, no redeploy to change
    try:
        scan_once(channel_url, state_file=None, notify=EmailNotifier().send,
                   fetch=..., )  # wire load_state/save_state in scan_once via DI
    except Exception:
        logging.exception("Scan failed")
```

The channel is deliberately **not** hardcoded — it's read from the
`YTA_CHANNEL_URL` app setting on every timer firing, so changing it is a
config edit, not a code change (see Step 6b below).

**State storage swap** — replace the local-file `_load_state`/`_save_state` in
`scanner.py` with Azure Table Storage (one row per channel, partition key =
channel, row key = fixed `"state"`), using the `azure-data-tables` SDK and the
Function App's own storage connection string (`AzureWebJobsStorage` app
setting — no new secret needed). This is the only structural change; `scan_once`'s
signature and decision logic stay identical.

Add to `requirements.txt`: `azure-functions`, `azure-data-tables`.

## Step 4 — Move secrets to App Settings (not `.env`)

```powershell
az functionapp config appsettings set -g rg-youtube-alerts -n <func-app-name> --settings `
  YTA_CHANNEL_URL="@ANINewsIndia" `
  YTA_SMTP_HOST="smtp.gmail.com" `
  YTA_SMTP_PORT="587" `
  YTA_SMTP_USERNAME="you@gmail.com" `
  YTA_SMTP_PASSWORD="<gmail app password>" `
  YTA_ALERT_TO="you@gmail.com"
```

For production hygiene, put the password in Key Vault and reference it with
`@Microsoft.KeyVault(...)` instead of a plaintext app setting — optional at
this scale.

## Step 5 — Deploy

```powershell
func azure functionapp publish <func-app-name>
```

## Step 6 — The on/off toggle (no code, no redeploy)

Azure Functions has a **native per-function disable switch** — this is your button.

**Portal:** Function App → Functions → `ScanTimer` → **Disable** / **Enable**
button at the top of the function's Overview page.

**CLI equivalent** (scriptable, e.g. from a phone via Cloud Shell):

```powershell
# Turn scanning OFF
az functionapp config appsettings set -g rg-youtube-alerts -n <func-app-name> `
  --settings "AzureWebJobs.ScanTimer.Disabled=true"

# Turn scanning back ON
az functionapp config appsettings set -g rg-youtube-alerts -n <func-app-name> `
  --settings "AzureWebJobs.ScanTimer.Disabled=false"
```

This flips an app setting the Functions host checks before firing the timer —
no redeploy, no code touch, and while disabled you pay **nothing** for that
function (Consumption plan bills executions, not idle time).

## Step 6b — Changing the YouTube channel (no code, no redeploy)

Since the channel is read from `YTA_CHANNEL_URL` on every run, switching the
watched channel is the same kind of edit as the toggle — a config change, not
a code change. Note the new channel takes effect on the *next* timer firing,
and because the state table is keyed by channel, the first scan after a
switch is treated as a fresh baseline (no notification), same as first-run
behavior locally.

**Portal:** Function App → Configuration → Application settings →
`YTA_CHANNEL_URL` → edit the value → Save.

**CLI equivalent:**

```powershell
az functionapp config appsettings set -g rg-youtube-alerts -n <func-app-name> `
  --settings "YTA_CHANNEL_URL=@SomeOtherChannel"
```

Accepts anything `normalize_channel_videos_url()` already accepts locally —
`@handle`, bare name, `UC...` id, or a full channel URL.

## Cost breakdown

| Item | Monthly cost |
|---|---|
| Function executions (~8,640/month @ 1-2s each) | $0 — within free grant (1M exec + 400K GB-s) |
| Storage account (Functions runtime + state table) | ~$0.05–$0.50 |
| Application Insights | Skip it (don't enable) → $0 |
| Email (Gmail SMTP) | $0 |
| **Total** | **~$0–$1/month** |

## Step 7 — Cleanup (if you ever want to stop entirely)

```powershell
az group delete -n rg-youtube-alerts --yes --no-wait
```

Deletes everything (Function App + Storage Account) in one shot, no orphaned
resources left behind to bill you.
