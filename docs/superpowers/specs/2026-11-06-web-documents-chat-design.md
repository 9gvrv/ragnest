# Ragnest Web — Documents & Chat — Design

**Date:** 2026-11-06
**Status:** proposed
**Scope:** `apps/web/` only. The API is complete through Milestone 6.

---

## 1. What this is

The frontend milestone that makes the workspace shell real: documents are
uploaded, indexed, and chatted with from `/workspaces/[id]`. The shell, upload
form, document list, and document detail page already exist; the chat column is
a static placeholder (`// TODO: wire to backend`). This milestone wires that
placeholder to the Milestone 6 SSE contract and adds the missing conversation
list, citation rendering, and document-indexing feedback.

The API is the authority for permissions, retrieval, and generation. The web
app never calls the API from client JS: reads happen in server components,
mutations and the stream go through route handlers.

---

## 2. Scope

**In:**

- Conversation list in the sidebar (the author's own chats, newest first),
  selection, new chat, delete.
- Asking a question from the composer and streaming the answer live.
- `sources` rendering with clickable `[n]` / `【n】` citation markers that
  jump to and highlight the cited source card.
- A streaming proxy at `app/api/.../messages` that forwards the API's SSE body
  without buffering.
- Document indexing state in the sidebar: `pending`, `indexing`, `ready`,
  `failed`; a retry action for non-ready documents; a light refresh watcher
  while indexing is in flight.
- Chat gate based on **at least one `ready` document**, not on document count.

**Out (non-goals):**

- Workspace-level chat visibility. Conversations remain private to their author
  (the API returns 404 to other members); the UI does not attempt sharing.
- Renaming conversations (no API endpoint; the first question sets the title).
- Markdown rendering of answers (no dependency; `whitespace-pre-wrap` only).
- Cross-conversation search, pagination, or infinite scroll.
- A web test framework (none exists; verification is lint + tsc + build +
  scripted HTTP/browser checks).
- Any new dependency.

---

## 3. What exists today (patterns of record)

- `app/(protected)/workspaces/[id]/(shell)/page.tsx` is a server component that
  reads the cookie, fetches workspace/members/me/documents, and renders
  `WorkspaceShell`. It sets `export const instant = false;` because it reads
  cookies.
- `WorkspaceShell` is a client component holding sidebar collapse, mobile
  drawer, section-open state, and composer focus.
- `ChatArea` and `ChatComposer` are present but static: `chats` and `messages`
  are empty arrays and `onSubmitQuestion` is a TODO.
- Documents are fully wired: `POST/DELETE app/api/workspaces/[id]/documents`,
  upload form, delete button, detail page.
- `lib/api.ts` has `request<T>` for JSON, `ApiError`, and `apiErrorResponse`.
  It buffers JSON bodies; it is not suitable for SSE.
- Routes use `RouteContext<'/api/...'>` with `await context.params`; pages use
  `PageProps<'/path/[seg]'>` with `await params` and `await searchParams`.
- `cacheComponents: true` and `partialPrefetching: true` are on; dynamic pages
  opt out of prerendering with `instant = false`.

---

## 4. Decisions

### D1 — Conversation selection is a query parameter, not a new route

`/workspaces/[id]?chat=<conversationId>` loads that conversation in the server
component; `/workspaces/[id]` is a new chat. This mirrors the existing
`?mine=true` filter, keeps the shell layout untouched, and makes reload/deep
links work without a second nested route. A missing/deleted `?chat` id
redirects to the bare workspace page; an unknown workspace still renders the
existing not-found/no-access states.

### D2 — The stream proxy forwards the upstream body

`app/api/workspaces/[id]/conversations/[conversationId]/messages/route.ts`
calls the API with `Accept: text/event-stream` and returns
`new Response(upstream.body, ...)` with `text/event-stream`,
`Cache-Control: no-cache, no-transform`, and `X-Accel-Buffering: no`.
The body is never read into memory. Pre-stream API failures (401/403/404/422/
429/503) arrive as ordinary JSON before any event; the proxy forwards their
status and `{detail, fields}` body unchanged.

### D3 — A conversation is created on the first question

A new chat is a transient UI state. On the first send, the client posts to the
conversations collection, receives the conversation, updates the URL with
`window.history.replaceState` (no navigation, so the stream is not torn down),
and then streams the message. The sidebar gains the conversation optimistically.
No server refresh is needed to read the answer back.

### D4 — The client owns the SSE parser

`lib/chat-stream.ts` decodes the body incrementally with `TextDecoder`, frames
on blank lines, and exposes typed callbacks for `sources`, `token`, `done`, and
`error`. Unknown events are ignored. `error` is terminal. The parser is pure
and independent of React so the framing rules stay in one place.

### D5 — Citation markers map to `sources[n - 1]`

Both ASCII `[1]` and full-width `【1】` markers (Groq emits the latter) are
rendered as buttons when `n` is within the citations array; anything else stays
literal text. Clicking a marker scrolls its source card into view and highlights
it. The API's `cited` list is informational; the rendered markers come from the
answer text.

### D6 — Chat unlocks on a ready document

A document row can exist while its chunks do not. The gate is therefore
`documents.some(d => d.embedding_status === "ready")`. Non-ready rows show
`queued`, `indexing…`, or `failed` and offer a retry (the API's reindex
endpoint). While anything is non-ready, `IndexingWatcher` calls
`router.refresh()` every few seconds (paused when the tab is hidden) so status
and the chat gate settle without a manual reload.

### D7 — Server props seed the client; the client owns the live exchange

`WorkspaceShell` maps the server conversation into UI messages and keeps them
in state. A change of `activeChatId` resets that state from the new server
payload. A client-created conversation does **not** change `activeChatId`, so
the optimistic messages survive; a later refresh (e.g. an upload) adopts the
persisted server truth. The sidebar title is updated locally after `done` using
the same rule as the API (whitespace-collapsed question, 80 chars).

### D8 — Stop means abort, and the API already handles it

While streaming, the send button becomes Stop. Aborting the fetch disconnects
the proxy stream, which makes the API persist the partial answer with
`finish_reason: "cancelled"`. The UI keeps the partial text and marks it
stopped. No second request is made.

### D9 — No new dependencies, no client-side API calls

All reads stay in the server component. All mutations and the stream go through
`app/api/**` route handlers that use the httpOnly cookie. Styling uses the
existing semantic tokens; no markdown, syntax-highlight, or SSE library is
added.

---

## 5. UX flows

### New chat

1. `/workspaces/[id]` renders the empty state and an enabled composer when at
   least one document is `ready`.
2. The person types and presses Enter or Send.
3. The question appears immediately; an assistant bubble shows a thinking state.
4. On the first event, sources replace the thinking state, tokens stream in.
5. On `done`, the composer unlocks and the chat appears in the sidebar with the
   question as its title (up to 80 chars).
6. The URL becomes `?chat=<id>`; reloading restores the exchange.

### Existing chat

Clicking a chat in the sidebar navigates to `?chat=<id>`. The server component
fetches the detail and seeds the message list in order. The active row is
marked with `aria-current="page"`. Deleting the active chat returns to the bare
workspace page.

### No matching context

`sources: []` + `no_context: true` streams the API's fixed refusal. The UI
renders it like any assistant message, with a muted "No sources found" note and
no source cards. The composer stays unlocked for a better question.

### Failures

- `401` at any point → full navigation to `/login?next=<current path>`.
- JSON `429` / `503` before the first event → inline alert ("The answer model is
  busy. Try again in a moment." / "The answer model is unavailable.").
- Terminal SSE `error` → keep the partial answer, show "The answer stopped
  early. Try again." and unlock the composer.
- Network failure → "Can't reach the server. Try again."

---

## 6. File map

New:

```text
apps/web/lib/chat-stream.ts                    # SSE framing + event types
apps/web/components/workspace/chat-message.tsx # message body, markers, sources
apps/web/components/workspace/indexing-watcher.tsx
apps/web/components/reindex-document-button.tsx
apps/web/components/delete-conversation-button.tsx
apps/web/app/api/workspaces/[id]/conversations/route.ts
apps/web/app/api/workspaces/[id]/conversations/[conversationId]/route.ts
apps/web/app/api/workspaces/[id]/conversations/[conversationId]/messages/route.ts
apps/web/app/api/workspaces/[id]/documents/[documentId]/reindex/route.ts
```

Modified:

```text
apps/web/lib/api.ts                            # chat types + calls, doc status
apps/web/app/(protected)/workspaces/[id]/(shell)/page.tsx
apps/web/components/workspace/workspace-shell.tsx
apps/web/components/workspace/chat-area.tsx
apps/web/components/workspace/chat-composer.tsx
apps/web/components/workspace/chats-section.tsx
apps/web/components/workspace/workspace-sidebar.tsx
apps/web/components/workspace/workspace-topbar.tsx
apps/web/components/workspace/documents-section.tsx
apps/web/components/workspace/icons.tsx
apps/web/AGENTS.md
```

---

## 7. Verification

Web has no test runner; every task ends with:

```bash
cd apps/web
pnpm lint && pnpm exec tsc --noEmit && pnpm build
```

Manual/scripted checks against the live API:

1. Sign in through `/api/auth/login` with a cookie jar; confirm the proxy
   returns `text/event-stream` and the expected `sources`/`token`/`done` frames.
2. Ask a grounded question: sources non-empty, answer cites `[1]`, reload keeps
   the exchange, the sidebar title becomes the question.
3. Ask an unrelated question with documents present: refusal with sources.
4. Create an empty workspace: chat is locked until a document is `ready`.
5. Upload a document: status moves to `ready` without a manual reload.
6. Stop mid-answer: partial text remains and the row is persisted as cancelled.
7. Second member: their sidebar has their own chats only; another author's
   `?chat` id redirects.
8. Delete a chat: it disappears; deleting the active one returns to a new chat.

---

## 8. Left to builder

- Exact stream cursor/thinking animation.
- Whether the source excerpt is clamped to two lines or three.
- Whether to show a score percentage at all (it is a cosine score, not a
  confidence).
- Whether the retry action is shown for `pending` as well as `failed` (the plan
  shows it for every non-ready row).
- Exact polling interval for `IndexingWatcher` (plan: 2.5s, stop after 40 tries).
