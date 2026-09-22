"""Azure Table Storage state backend used by the Azure Functions deployment.

Drop-in replacement for :class:`youtubealerts.scanner.FileStateStore`: one row per
channel (partition key = hashed channel URL, row key = ``state``) stored in the
Function App's own storage account, so no extra secret or resource is needed.
"""

import hashlib
import logging
import os
from typing import Optional, Tuple

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableClient, UpdateMode

from .models import Video

logger = logging.getLogger(__name__)

DEFAULT_TABLE_NAME = "ytastate"
ROW_KEY = "state"


def _partition_key(channel_url: str) -> str:
    # Channel URLs contain '/' and '?', which Table Storage forbids in keys.
    return hashlib.sha256(channel_url.encode("utf-8")).hexdigest()


class TableStateStore:
    """Remembers the last seen video per channel in Azure Table Storage."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        table_name: Optional[str] = None,
    ) -> None:
        connection_string = connection_string or os.environ["AzureWebJobsStorage"]
        table_name = table_name or os.environ.get("YTA_STATE_TABLE", DEFAULT_TABLE_NAME)
        self._client = TableClient.from_connection_string(connection_string, table_name)
        try:
            self._client.create_table()
        except ResourceExistsError:
            pass

    def load(self, channel_url: str) -> Tuple[Optional[str], Optional[bool]]:
        try:
            entity = self._client.get_entity(_partition_key(channel_url), ROW_KEY)
        except ResourceNotFoundError:
            return None, None
        video_id = entity.get("video_id")
        members_only = entity.get("members_only")
        return (
            video_id if isinstance(video_id, str) else None,
            members_only if isinstance(members_only, bool) else None,
        )

    def save(self, channel_url: str, video: Video) -> None:
        entity = {
            "PartitionKey": _partition_key(channel_url),
            "RowKey": ROW_KEY,
            "channel_url": channel_url,
            "video_id": video.video_id,
        }
        # Unknown membership is stored as an absent property, mirroring load()'s None.
        if isinstance(video.members_only, bool):
            entity["members_only"] = video.members_only
        self._client.upsert_entity(entity, mode=UpdateMode.REPLACE)
