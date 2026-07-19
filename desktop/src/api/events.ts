// Event names shared with the Python bridge (boot.py / orchestrator_adapter.py).

import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export const EVENTS = {
  bootProgress: "boot://progress",
  bootComplete: "boot://complete",
  bootError: "boot://error",
  draftStatus: "draft://status",
  draftRefresh: "draft://refresh",
  draftHeartbeat: "draft://heartbeat",
  appError: "app://error",
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

export function on<T>(
  event: string,
  handler: (payload: T) => void,
): Promise<UnlistenFn> {
  return listen<T>(event, (e) => handler(e.payload));
}
