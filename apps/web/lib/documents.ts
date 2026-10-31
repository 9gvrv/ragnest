import type { ApiDocument, ApiRole } from "@/lib/api";

export const MAX_DOCUMENT_BYTES = 5 * 1024 * 1024;

export const DOCUMENT_EXTENSIONS = [".txt", ".md", ".pdf"] as const;

const numberFormat = new Intl.NumberFormat("en-GB");

export function isSupportedDocument(filename: string) {
  const lowered = filename.toLowerCase();
  return DOCUMENT_EXTENSIONS.some((extension) => lowered.endsWith(extension));
}

/**
 * Mirrors the API's delete rule: the uploader, or a creator/admin, may remove
 * a document. Presentation only — the API remains the authority.
 */
export function canManageDocument(
  role: ApiRole,
  userId: string,
  document: Pick<ApiDocument, "uploaded_by">,
) {
  return (
    document.uploaded_by === userId || role === "creator" || role === "admin"
  );
}

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${numberFormat.format(bytes)} B`;
  const kilobytes = bytes / 1024;
  if (kilobytes < 1024) {
    return `${kilobytes < 10 ? kilobytes.toFixed(1) : Math.round(kilobytes)} KB`;
  }
  const megabytes = kilobytes / 1024;
  return `${megabytes < 10 ? megabytes.toFixed(1) : Math.round(megabytes)} MB`;
}

export function formatCount(value: number) {
  return numberFormat.format(value);
}

/** Turn the API's status into a sentence a person can act on. */
export function documentFailure(status: number, detail?: string | null) {
  switch (status) {
    case 403:
      return "You don't have permission to do that in this workspace.";
    case 404:
      return "This document no longer exists.";
    case 413:
      return "That file is larger than 5 MB.";
    case 415:
      return "That file type isn't supported. Use a .txt, .md, or .pdf file.";
    case 422:
      return detail ?? "That file couldn't be read. Try another one.";
    default:
      return detail ?? "Something went wrong. Try again.";
  }
}
