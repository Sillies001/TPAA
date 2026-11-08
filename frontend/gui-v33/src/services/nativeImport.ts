import type { ImportTicketDTO } from "../generated/g4-batch.ts";

const requestNativeSelection = (kind: "FILE" | "DIRECTORY"): Promise<string> => new Promise(
  (resolve, reject) => {
    const timeout = window.setTimeout(() => {
      window.removeEventListener("tpaa-native-import-result", completed as EventListener);
      reject(new Error("NATIVE_IMPORT_BRIDGE_TIMEOUT"));
    }, 30_000);
    const completed = (event: Event): void => {
      window.clearTimeout(timeout);
      window.removeEventListener("tpaa-native-import-result", completed as EventListener);
      const detail = (event as CustomEvent<unknown>).detail;
      if (typeof detail !== "string") {
        reject(new Error("NATIVE_IMPORT_BRIDGE_RESPONSE_INVALID"));
        return;
      }
      resolve(detail);
    };
    window.addEventListener("tpaa-native-import-result", completed as EventListener, { once: true });
    window.location.assign(
      kind === "FILE"
        ? "/ui?tpaa_native_action=select-file"
        : "/ui?tpaa_native_action=select-directory",
    );
  },
);

export const selectImportSource = async (
  kind: "FILE" | "DIRECTORY",
): Promise<ImportTicketDTO | null> => {
  const raw = await requestNativeSelection(kind);
  const parsed: unknown = JSON.parse(raw);
  if (parsed === null) return null;
  if (
    typeof parsed === "object"
    && parsed !== null
    && typeof (parsed as Record<string, unknown>).error === "string"
  ) {
    throw new Error(String((parsed as Record<string, unknown>).error));
  }
  if (
    typeof parsed !== "object"
    || parsed === null
    || typeof (parsed as Record<string, unknown>).ticket_id !== "string"
    || (parsed as Record<string, unknown>).local_path !== null
  ) {
    throw new Error("NATIVE_IMPORT_TICKET_INVALID");
  }
  return parsed as ImportTicketDTO;
};
