import type { ApiMember, ApiRole } from "@/lib/api";

/**
 * Two letters for the avatar: the first two characters of the local part of an
 * email, or the first two characters of a workspace name. Presentation only.
 */
export function initialsFromEmail(email: string) {
  const local = email.split("@")[0]?.trim();
  if (!local) return "?";
  return local.slice(0, 2).toUpperCase();
}

export function initialsFromName(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

/**
 * Mirrors the API's member-removal rule: a creator may remove admins and
 * members, an admin may remove plain members, nobody removes themselves or the
 * creator. Presentation only — the API remains the authority.
 */
export function canRemoveMember(
  myRole: ApiRole,
  myUserId: string,
  member: ApiMember,
) {
  if (member.user_id === myUserId) return false; // never yourself
  if (member.role === "creator") return false; // never the creator
  if (myRole === "creator") return true;
  if (myRole === "admin") return member.role === "member";
  return false; // plain members manage nobody
}

/** The file-type tile in the document list: PDF, MD, TXT, or FILE. */
export function documentKind(filename: string) {
  const extension = filename.split(".").pop()?.toLowerCase();
  if (extension === "pdf") return "PDF";
  if (extension === "md" || extension === "markdown") return "MD";
  if (extension === "txt" || extension === "text") return "TXT";
  return "FILE";
}
