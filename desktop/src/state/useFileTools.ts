import { useCallback, useState } from "react";

import {
  exportDraft,
  locateMtgaData,
  saveExportFile,
} from "../api/client";
import { t } from "../i18n/useLanguage";

// The legacy File menu's tools (src/ui/menu_bar.py): draft export and the
// native file/directory pickers. Path selection uses the Tauri dialog plugin;
// the actual write happens in Python so the fs plugin's scope doesn't have to
// cover every user-writable path. Outside Tauri the plugin import rejects, and
// the failure surfaces as `message` rather than breaking the page.

async function pickSavePath(
  defaultPath: string,
  extension: string,
): Promise<string | null> {
  const { save } = await import("@tauri-apps/plugin-dialog");
  return save({
    defaultPath,
    filters: [{ name: extension.toUpperCase(), extensions: [extension] }],
  });
}

async function pickPath(
  directory: boolean,
  title: string,
): Promise<string | null> {
  const { open } = await import("@tauri-apps/plugin-dialog");
  const picked = await open({
    directory,
    multiple: false,
    title,
    filters: directory ? undefined : [{ name: "Log", extensions: ["log"] }],
  });
  return typeof picked === "string" ? picked : null;
}

export function useFileTools() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const runExport = useCallback(async (format: "csv" | "json") => {
    setBusy(true);
    try {
      const result = await exportDraft(format);
      if (!result.ok) {
        setMessage(result.message);
        return;
      }
      const path = await pickSavePath(result.fileName, format);
      if (!path) return;
      const saved = await saveExportFile(path, result.text);
      setMessage(saved.message);
    } catch (err) {
      setMessage(t("file.exportFailed", { err: String(err) }));
    } finally {
      setBusy(false);
    }
  }, []);

  const browseLogFile = useCallback(async (): Promise<string | null> => {
    setBusy(true);
    try {
      return await pickPath(false, t("file.selectLog"));
    } catch (err) {
      setMessage(t("file.pickerFailed", { err: String(err) }));
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  const browseMtgaData = useCallback(async (): Promise<string | null> => {
    setBusy(true);
    try {
      const folder = await pickPath(true, t("file.selectDataFolder"));
      if (!folder) return null;
      const result = await locateMtgaData(folder);
      setMessage(result.message);
      return result.ok ? result.path : null;
    } catch (err) {
      setMessage(t("file.dataFolderFailed", { err: String(err) }));
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  return { busy, message, runExport, browseLogFile, browseMtgaData };
}
