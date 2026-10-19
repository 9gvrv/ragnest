import { clearSessionToken } from "@/lib/session";

export async function POST() {
  await clearSessionToken();
  return new Response(null, { status: 204 });
}
