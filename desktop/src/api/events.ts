// Event names shared with the Python bridge (boot.py / orchestrator_adapter.py).
// Each payload interface mirrors the like-named _VM in viewmodels.py — the emit
// sites construct those models, and test_bridge_serialization.py asserts no emit
// site passes a bare dict.

import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export const EVENTS = {
  bootProgress: "boot://progress",
  bootComplete: "boot://complete",
  bootError: "boot://error",
  draftStatus: "draft://status",
  draftRefresh: "draft://refresh",
  draftHeartbeat: "draft://heartbeat",
  appError: "app://error",
  datasetsUpdated: "datasets://updated",
  updateAvailable: "update://available",
} as const;

export interface BootProgressPayload {
  message: string;
}

export interface BootCompletePayload {
  foundDraft: boolean;
  eventSet: string;
  eventType: string;
  pack: number;
  pick: number;
  hasDataset: boolean;
}

export interface BootErrorPayload {
  message: string;
}

export interface StatusPayload {
  text: string;
}

export interface RefreshPayload {
  seq: number;
}

export interface HeartbeatPayload {
  logMtime: number;
  logName: string;
}

export interface AppErrorPayload {
  message: string;
}

export interface DatasetsUpdatedPayload {
  updatedCount: number;
}

export interface UpdateAvailablePayload {
  latestVersion: string;
  releaseUrl: string;
}

export function on<T>(
  event: string,
  handler: (payload: T) => void,
): Promise<UnlistenFn> {
  return listen<T>(event, (e) => handler(e.payload));
}
