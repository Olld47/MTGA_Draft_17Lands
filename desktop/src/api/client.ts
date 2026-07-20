// Typed pyInvoke wrappers for every mtga_bridge command.

import { Channel } from "@tauri-apps/api/core";
import { pyInvoke } from "tauri-plugin-pytauri-api";

import type {
  Ack,
  AvailableSets,
  BootStatus,
  CompareState,
  DatasetList,
  DeckExport,
  DeckState,
  DownloadProgress,
  DownloadResult,
  DraftLogList,
  DraftRecord,
  DraftState,
  FilterOptions,
  Recap,
  SampleHand,
  SealedAction,
  SealedDeckTech,
  SealedState,
  Settings,
  SettingsPatch,
  SimResult,
  TakenCards,
  TierAction,
  TierLists,
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

// --- Post-draft recap -------------------------------------------------------

export const getRecap = () => pyInvoke<Recap>("get_recap");

export const getDraftRecord = (draftId: string) =>
  pyInvoke<DraftRecord>("get_draft_record", { draftId });

// --- Custom deck builder ------------------------------------------------------

export const getDeckState = () => pyInvoke<DeckState>("get_deck_state");

export const deckRefreshPool = () => pyInvoke<DeckState>("deck_refresh_pool");

export const deckMoveCard = (cardName: string, toSideboard: boolean) =>
  pyInvoke<DeckState>("deck_move_card", { cardName, toSideboard });

export const deckClear = () => pyInvoke<DeckState>("deck_clear");

export const deckAddBasic = (colorName: string) =>
  pyInvoke<DeckState>("deck_add_basic", { colorName });

export const deckRemoveBasic = (colorName: string) =>
  pyInvoke<DeckState>("deck_remove_basic", { colorName });

export const deckSimulate = () => pyInvoke<SimResult>("deck_simulate");

export const deckAutoOptimize = () => pyInvoke<SimResult>("deck_auto_optimize");

export const deckAutoLands = () => pyInvoke<SimResult>("deck_auto_lands");

export const deckSampleHand = () => pyInvoke<SampleHand>("deck_sample_hand");

export const deckExport = () => pyInvoke<DeckExport>("deck_export");

// --- Sealed studio ------------------------------------------------------------

export const getSealedState = () => pyInvoke<SealedState>("get_sealed_state");

export const sealedReloadPool = () =>
  pyInvoke<SealedState>("sealed_reload_pool");

export const sealedAutoGenerate = () =>
  pyInvoke<SealedAction>("sealed_auto_generate");

export const sealedSelectVariant = (name: string) =>
  pyInvoke<SealedAction>("sealed_select_variant", { name });

export const sealedCreateVariant = (name: string, copyFrom?: string) =>
  pyInvoke<SealedAction>("sealed_create_variant", {
    name,
    copyFrom: copyFrom ?? null,
  });

export const sealedDeleteVariant = (name: string) =>
  pyInvoke<SealedAction>("sealed_delete_variant", { name });

export const sealedRenameVariant = (oldName: string, newName: string) =>
  pyInvoke<SealedAction>("sealed_rename_variant", { oldName, newName });

export const sealedMoveCard = (
  cardName: string,
  toSideboard: boolean,
  count = 1,
) => pyInvoke<SealedAction>("sealed_move_card", { cardName, toSideboard, count });

export const sealedClearDeck = () => pyInvoke<SealedAction>("sealed_clear_deck");

export const sealedAutoLands = () => pyInvoke<SealedAction>("sealed_auto_lands");

export const sealedImportDeck = (text: string) =>
  pyInvoke<SealedAction>("sealed_import_deck", { text });

export const sealedExport = () => pyInvoke<DeckExport>("sealed_export");

export const sealedExportSealeddeck = () =>
  pyInvoke<SealedDeckTech>("sealed_export_sealeddeck");

// --- Compare workspace ---------------------------------------------------------

export const getCompareState = () => pyInvoke<CompareState>("get_compare_state");

export const compareAddCard = (name: string) =>
  pyInvoke<CompareState>("compare_add_card", { name });

export const compareRemoveCard = (name: string) =>
  pyInvoke<CompareState>("compare_remove_card", { name });

export const compareClear = () => pyInvoke<CompareState>("compare_clear");

// --- Tier lists ------------------------------------------------------------------

export const getTierLists = (setCode = "") =>
  pyInvoke<TierLists>("get_tier_lists", { setCode });

export const importTierList = (url: string, label: string) =>
  pyInvoke<TierAction>("import_tier_list", { url, label });

export const deleteTierLists = (fileNames: string[]) =>
  pyInvoke<TierAction>("delete_tier_lists", { fileNames });
