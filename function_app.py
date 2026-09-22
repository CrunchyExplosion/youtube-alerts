"""Azure Functions entry point: timer-triggered wrapper around scan_once()."""

import logging
import os

import azure.functions as func

from youtubealerts.scanner import EmailNotifier, scan_once
from youtubealerts.table_state import TableStateStore

app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 */5 * * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def ScanTimer(timer: func.TimerRequest) -> None:
    # Read on every run so changing the channel is a config edit, not a redeploy.
    channel_url = os.environ["YTA_CHANNEL_URL"]
    try:
        scan_once(channel_url, TableStateStore(), EmailNotifier().send)
    except Exception:
        logging.exception("Scan failed for %s", channel_url)
