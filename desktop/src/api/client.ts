// Typed pyInvoke wrappers for every mtga_bridge command.

import { Channel } from "@tauri-apps/api/core";
import { pyInvoke } from "tauri-plugin-pytauri-api";

import type {
  Ack,
  AvailableSets,
  BootStatus,
  DatasetList,
  DownloadProgress,
  DownloadResult,
  DraftLogList,
  DraftState,
  FilterOptions,
  Settings,
  SettingsPatch,
  TakenCards,
} from "./types";

export const getBootStatus = () => pyInvoke<BootStatus>("get_boot_status");

export const getDraftState = () => pyInvoke<DraftState>("get_draft_state");

export const getTakenCards = () => pyInvoke<TakenCards>("get_taken_cards");

export const forceReload = () => pyInvoke<Ack>("force_reload");

export const setLogFile = (path: string) =>
  pyInvoke<Ack>("set_log_file", { path });

export const listDraftLogs = () => pyInvoke<DraftLogList>("list_draft_logs");

export const getSettings = () => pyInvoke<Settings>("get_settings");

export const setSettings = (patch: SettingsPatch) =>
  pyInvoke<Settings>("set_settings", patch);

export const getFilterOptions = () =>
  pyInvoke<FilterOptions>("get_filter_options");

export const listDatasets = () => pyInvoke<DatasetList>("list_datasets");

export const listAvailableSets = () =>
  pyInvoke<AvailableSets>("list_available_sets");

export const selectDataset = (path: string) =>
  pyInvoke<Ack>("select_dataset", { path });

export const deleteDataset = (path: string) =>
  pyInvoke<DatasetList>("delete_dataset", { path });

export function downloadDataset(
  setCode: string,
  eventType: string,
  userGroup: string,
  onProgress: (p: DownloadProgress) => void,
): Promise<DownloadResult> {
  const channel = new Channel<DownloadProgress>(onProgress);
  return pyInvoke<DownloadResult>("download_dataset", {
    request: { setCode, eventType, userGroup },
    channel,
  });
}
