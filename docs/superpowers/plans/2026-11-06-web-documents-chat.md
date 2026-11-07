# Documents & Chat — Web Implementation Plan

> **For agentic workers:** This plan is executed inline by one agent (the
> person asked for autonomy). Steps are concrete and verifiable. The mentor-mode
> rule is relaxed for this milestone by explicit request; each commit is small
> enough to review on its own.

**Goal:** Wire the workspace shell's chat column to the Milestone 6 API:
conversation list, live SSE answers, clickable citations, and document indexing
feedback.

**Architecture:** Server components read the httpOnly cookie and fetch the API
through `lib/api.ts`. Mutations and the SSE stream go through `app/api/**`
route handlers. The browser never calls the API directly.

**Tech stack:** Next.js 16 App Router, React 19, TypeScript, Tailwind 4,
pnpm. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-06-web-documents-chat-design.md`

## Global constraints

- Reads: `getSessionToken()` + `lib/api.ts`; page keeps `export const instant = false;`.
- Mutations/stream: route handlers under `app/api/**`, cookie in, API out.
- Dates: `parseApiDate()` only.
- 401 during render → `redirect("/login?next=...")`; during a mutation → client
  full navigation to login.
- No client JS reads the JWT.
- Existing semantic tokens only (`background`, `surface`, `elevated`, `border`,
  `control`, `foreground`, `muted`, `accent`, `danger`).
- `pnpm lint && pnpm exec tsc --noEmit && pnpm build` clean at every commit.
- No new dependencies.

---

## Task 0: Branch and preserve existing polish

- [x] Create `feat/web-documents-chat` from `main`.
- [x] Commit the four pre-existing workspace style edits as their own commit
  (`style(workspace): refine sidebar row alignment and scrollbars`) so they do
  not mix with milestone work.
- [x] Commit this design and plan.

---

## Task 1: API client surface

**Files:**
- Modify: `apps/web/lib/api.ts`

- [x] **Step 1:** Add chat types: `ApiCitation`, `ApiConversation`,
  `ApiMessage`, `ApiConversationDetail`.
- [x] **Step 2:** Add `embedding_status` and `indexed_at` to `ApiDocument`.
- [x] **Step 3:** Add calls: `listConversations`, `createConversation`,
  `getConversation`, `deleteConversation`, `reindexDocument`.
- [x] **Step 4:** Add `streamConversationMessage(token, workspaceId,
  conversationId, content)` that POSTs with `Accept: text/event-stream` and
  returns the raw `Response` (no body read). On network failure it throws
  `ApiError(0, ...)`.
- [x] **Step 5:** `pnpm exec tsc --noEmit`. Commit
  `feat(web): add chat api client and document status`.

---

## Task 2: Proxy route handlers

**Files:**
- Create: `apps/web/app/api/workspaces/[id]/conversations/route.ts` (POST)
- Create: `apps/web/app/api/workspaces/[id]/conversations/[conversationId]/route.ts` (DELETE)
- Create: `apps/web/app/api/workspaces/[id]/conversations/[conversationId]/messages/route.ts` (POST)
- Create: `apps/web/app/api/workspaces/[id]/documents/[documentId]/reindex/route.ts` (POST)

- [x] **Step 1:** Each handler reads the cookie and returns 401
  `{detail: "Not authenticated"}` when absent.
- [x] **Step 2:** Conversation create forwards `{title}` (or `{}`); delete
  returns 204; reindex returns the API's 202 body.
- [x] **Step 3:** The messages handler validates `{content: string}`, calls
  `streamConversationMessage`, and:
  - on a non-OK upstream response, forwards its JSON body and status;
  - on OK, returns `new Response(response.body, { headers: { "Content-Type":
    "text/event-stream; charset=utf-8", "Cache-Control": "no-cache,
    no-transform", "X-Accel-Buffering": "no" } })`.
- [x] **Step 4:** `pnpm exec next typegen` to register the new routes, then
  `tsc --noEmit`. Commit `feat(web): proxy chat and reindex mutations`.

---

## Task 3: Server page loads conversations

**Files:**
- Modify: `apps/web/app/(protected)/workspaces/[id]/(shell)/page.tsx`
- Modify: `apps/web/components/workspace/workspace-shell.tsx` (props only)

- [x] **Step 1:** Read `chat` from `searchParams`; fetch `listConversations`
  alongside the existing parallel fetches.
- [x] **Step 2:** When `chat` is present, fetch `getConversation`. Map API
  errors: 401 → login redirect, 404/422 → `redirect` to the bare workspace
  page, 403 → existing `NoAccess`.
- [x] **Step 3:** Compute `hasReadyDocuments` from `embedding_status === "ready"`.
- [x] **Step 4:** Pass `conversations`, `activeChatId`, `activeChatTitle`,
  `initialMessages`, and `hasReadyDocuments` into `WorkspaceShell`.
- [x] **Step 5:** Remove the "no chat backend yet" placeholder comment and empty
  arrays. `tsc --noEmit`; commit `feat(web): load conversations in the workspace page`.

---

## Task 4: SSE parser and chat state machine

**Files:**
- Create: `apps/web/lib/chat-stream.ts`
- Modify: `apps/web/components/workspace/workspace-shell.tsx`
- Modify: `apps/web/components/workspace/chat-area.tsx`
- Modify: `apps/web/components/workspace/chat-composer.tsx`
- Modify: `apps/web/components/workspace/icons.tsx` (add a stop icon)

- [x] **Step 1:** Implement `readChatStream(response, onEvent)` — incremental
  `TextDecoder`, blank-line framing, JSON parse, typed events:
  `sources`, `token`, `done`, `error`; ignore unknown event names; flush the
  trailing frame.
- [x] **Step 2:** In `WorkspaceShell`, hold `chats`, `selectedChatId`,
  `messages`, `streaming`, `failure`, and refs for the conversation id and
  `AbortController`.
- [x] **Step 3:** On send: append the user message and a streaming assistant
  placeholder; create the conversation if there is none; keep the URL unchanged
  while streaming; POST the stream; feed events into the message list; call
  `router.replace(...?chat=<id>)` only after the stream settles.
- [x] **Step 4:** On `sources` adopt the real assistant id and citations; on
  `token` append; on `done` set `finishReason`, update the sidebar title to
  `question.split(/\s+/).join(" ").slice(0, 80)` while it is the default, and
  unlock; on `error` keep partial text, show the alert, unlock.
- [x] **Step 5:** Stop button aborts the fetch, marks the message `cancelled`,
  and unlocks. 401 → login with `?next=`; 429/503 JSON → the mapped alert.
- [x] **Step 6:** Reset messages from server props when `activeChatId` changes
  (not while streaming). `tsc --noEmit`; commit
  `feat(web): stream chat answers`.

---

## Task 5: Message rendering and clickable citations

**Files:**
- Create: `apps/web/components/workspace/chat-message.tsx`
- Modify: `apps/web/components/workspace/chat-area.tsx`

- [x] **Step 1:** Render user messages as right-aligned surface cards;
  assistant messages plain, preserving newlines.
- [x] **Step 2:** Split assistant content on `/(\[\d+\]|【\d+】)/`; render a
  marker as a button when `1 <= n <= citations.length`, otherwise literal text.
- [x] **Step 3:** Clicking a marker scrolls its source card into view and
  highlights it (`ring-1 ring-accent`), toggling off on a second click.
- [x] **Step 4:** Render source cards with `[n]`, filename, clamped excerpt,
  and score; show "No sources found" when `finish_reason === "no_context"`.
- [x] **Step 5:** Streaming placeholder: three pulsing dots behind
  `motion-reduce:animate-none`; stopped answers show a muted "Stopped."
- [x] **Step 6:** Auto-scroll to the bottom only while the reader is already
  near it. `tsc --noEmit`; commit `feat(web): render citations in chat answers`.

---

## Task 6: Sidebar chat list and topbar title

**Files:**
- Modify: `apps/web/components/workspace/chats-section.tsx`
- Modify: `apps/web/components/workspace/workspace-sidebar.tsx`
- Modify: `apps/web/components/workspace/workspace-topbar.tsx`
- Create: `apps/web/components/delete-conversation-button.tsx`

- [x] **Step 1:** Chat rows become `Link`s to `?chat=<id>` with
  `aria-current="page"` and an active background.
- [x] **Step 2:** New chat becomes a `Link` to the bare workspace path that
  also focuses the composer.
- [x] **Step 3:** Add a hover/focus delete control per row (confirm, then
  DELETE the route handler). Deleting the active chat navigates to the bare
  workspace path; others `router.refresh()`.
- [x] **Step 4:** Topbar shows the active conversation title, or "New chat".
- [x] **Step 5:** `tsc --noEmit`; commit `feat(web): add conversation list and title`.

---

## Task 7: Document indexing state

**Files:**
- Modify: `apps/web/components/workspace/documents-section.tsx`
- Modify: `apps/web/components/workspace/workspace-shell.tsx`
- Modify: `apps/web/components/workspace/chat-area.tsx`
- Create: `apps/web/components/workspace/indexing-watcher.tsx`
- Create: `apps/web/components/reindex-document-button.tsx`
- Modify: `apps/web/components/workspace/icons.tsx` (retry icon)

- [x] **Step 1:** Show `queued` / `indexing…` / `failed` beside a non-ready
  document; keep `ready` rows as they are.
- [x] **Step 2:** Add the retry action for every non-ready row; it POSTs the
  reindex handler, shows a failure inline on error, and refreshes on 202.
- [x] **Step 3:** Add `IndexingWatcher` (2.5s interval, max 40 ticks, paused when
  `document.visibilityState !== "visible"`); mount it while any document is
  non-ready.
- [x] **Step 4:** Gate the chat on `hasReadyDocuments`; the locked copy
  distinguishes "no documents" from "documents still indexing".
- [x] **Step 5:** `tsc --noEmit`; commit `feat(web): show document indexing state`.

---

## Task 8: Verification and docs

**Files:**
- Modify: `apps/api/AGENTS.md` / `apps/web/AGENTS.md` only if a pattern changed
- Modify: `AGENTS.md` (roadmap)
- Modify: `docs/progress.md`
- Modify: the spec status to `built`

- [x] **Step 1:** `cd apps/web && pnpm lint && pnpm exec tsc --noEmit && pnpm build`.
- [x] **Step 2:** Scripted API check: log in through the web route handler with
  a cookie jar, then POST the messages proxy and assert `text/event-stream`
  plus `sources`/`token`/`done`.
- [x] **Step 3:** Browser checks from spec §7 (new chat, reload, switch, delete,
  stop, no-context, empty workspace, indexing).
- [x] **Step 4:** Update `apps/web/AGENTS.md` (chat patterns, streaming proxy,
  citation rules), the root roadmap, `docs/progress.md`, and mark the spec
  `built`.
- [x] **Step 5:** Commit `docs(web): document documents and chat milestone`.
