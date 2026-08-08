import os
import json
import gzip
import requests
import logging
from src import constants
from src.configuration import write_configuration

logger = logging.getLogger(__name__)


def _dataset_set_format(key: str):
    """Split a manifest key (SET_FORMAT_GROUP) into (set, format).

    Returns (None, None) for anything that does not follow the shape."""
    parts = key.rsplit("_", 2)
    if len(parts) != 3:
        return None, None
    return parts[0], parts[1]


def _is_live_dataset(key: str, live_formats_by_expansion: dict) -> bool:
    """True when the manifest dataset matches a currently live draft format.

    Matches expansion names and format strings exactly — a rotated set's cube
    (e.g. "Cube - Powered") must never be served for a live one ("Cube -
    Planar"), and a live set's Sealed/ArenaDirect datasets stay excluded."""
    set_part, fmt_part = _dataset_set_format(key)
    if not set_part:
        return False
    return fmt_part in live_formats_by_expansion.get(set_part, [])


class DatasetUpdater:
    def __init__(self, config):
        self.config = config
        self.local_manifest_path = os.path.join(
            constants.SETS_FOLDER, "local_manifest.json"
        )

    def get_local_manifest(self):
        if os.path.exists(self.local_manifest_path):
            try:
                with open(self.local_manifest_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"datasets": {}}

    def save_local_manifest(self, manifest_data):
        with open(self.local_manifest_path, "w") as f:
            json.dump(manifest_data, f)

    def _fetch_live_formats(self) -> dict:
        """live_formats_by_expansion from 17Lands, or {} when unreachable."""
        try:
            resp = requests.get(constants.SEVENTEENLANDS_DATA_FILTERS_URL, timeout=5)
            resp.raise_for_status()
            live = resp.json().get("live_formats_by_expansion") or {}
            return live if isinstance(live, dict) else {}
        except Exception as e:
            logger.warning(f"Failed to fetch live formats: {e}")
            return {}

    def sync_datasets(self, progress_callback):
        """Fetches remote manifest and downloads missing/updated sets.

        A fresh install only needs the sets that are live right now, so the
        manifest is filtered to the draft formats 17Lands reports as currently
        playable (live_formats_by_expansion). If that endpoint is unreachable
        we fall back to the manifest's own active_sets, then to everything."""
        try:
            # Check pipeline health first to notify user if there are backend issues
            try:
                report_url = constants.REMOTE_DATASET_BASE_URL + "report.json"
                report_resp = requests.get(report_url, timeout=3)
                if report_resp.status_code == 200:
                    report_data = report_resp.json()
                    if report_data.get("pipeline_run", {}).get("status") == "FAILED":
                        progress_callback(
                            "⚠️ Server sync failed today. Using cached data."
                        )
            except Exception as health_e:
                logger.debug(f"Failed to fetch health report (non-fatal): {health_e}")

            progress_callback("Checking for official dataset updates...")
            resp = requests.get(constants.REMOTE_MANIFEST_URL, timeout=5)
            resp.raise_for_status()
            remote_manifest = resp.json()

            local_manifest = self.get_local_manifest()

            if "active_sets" in remote_manifest:
                local_manifest["active_sets"] = remote_manifest["active_sets"]

            remote_datasets = remote_manifest.get("datasets", {})

            live = self._fetch_live_formats()
            if live:
                scoped = {
                    key: info
                    for key, info in remote_datasets.items()
                    if _is_live_dataset(key, live)
                }
            else:
                active_sets = remote_manifest.get("active_sets") or []
                if active_sets:
                    scoped = {
                        key: info
                        for key, info in remote_datasets.items()
                        if (_dataset_set_format(key)[0] or "") in active_sets
                    }
                else:
                    scoped = remote_datasets  # no live info at all → download all

            updates_made = False

            for key, file_info in scoped.items():
                remote_hash = file_info.get("hash")
                remote_filename = file_info.get("filename")

                local_filename = remote_filename.replace(".gz", "")
                local_filepath = os.path.join(constants.SETS_FOLDER, local_filename)

                local_hash = local_manifest.get("datasets", {}).get(key, {}).get("hash")
                file_missing = not os.path.exists(local_filepath)

                if file_missing or local_hash != remote_hash:
                    progress_callback(f"Downloading {key}...")

                    file_url = constants.REMOTE_DATASET_BASE_URL + remote_filename
                    gz_resp = requests.get(file_url, timeout=15)
                    gz_resp.raise_for_status()

                    import gzip

                    json_data = gzip.decompress(gz_resp.content)

                    tmp_path = local_filepath + ".tmp"
                    with open(tmp_path, "wb") as f:
                        f.write(json_data)
                    os.replace(tmp_path, local_filepath)

                    if "datasets" not in local_manifest:
                        local_manifest["datasets"] = {}
                    local_manifest["datasets"][key] = file_info
                    updates_made = True

            self.save_local_manifest(local_manifest)

            if updates_made:
                progress_callback("Datasets updated successfully.")

        except Exception as e:
            logger.error(f"Failed to sync datasets: {e}")
            progress_callback("Skipped dataset sync (Network Error).")
