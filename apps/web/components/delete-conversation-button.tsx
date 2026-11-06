"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { TrashIcon } from "@/components/workspace/icons";

function failureMessage(status: number) {
  switch (status) {
    case 403:
      return "You can't delete this chat.";
    case 404:
      return "That chat no longer exists.";
    default:
      return "Couldn't delete the chat. Try again.";
  }
}

export function DeleteConversationButton({
  workspaceId,
  conversationId,
  title,
  active,
  onDeleted,
}: {
  workspaceId: string;
  conversationId: string;
  title: string;
  active: boolean;
  onDeleted: (conversationId: string) => void;
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function remove() {
    const confirmed = window.confirm(
      `Delete "${title}"? Its messages go with it, and this can't be undone.`,
    );
    if (!confirmed) return;

    setPending(true);
    setFailure(null);

    try {
      const response = await fetch(
        `/api/workspaces/${workspaceId}/conversations/${conversationId}`,
        { method: "DELETE" },
      );

      if (response.status === 401) {
        const next = encodeURIComponent(
          window.location.pathname + window.location.search,
        );
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/login?next=${next}`);
        return;
      }

      if (response.status === 204) {
        onDeleted(conversationId);
        if (active) {
          // Drop the deleted conversation's id from the URL.
          router.replace(`/workspaces/${workspaceId}`);
          router.refresh();
        } else {
          router.refresh();
        }
        return;
      }

      setFailure(failureMessage(response.status));
    } catch {
      setFailure("Can't reach the server. Try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <span className="flex flex-col items-end">
      <button
        type="button"
        onClick={remove}
        disabled={pending}
        aria-label={`Delete ${title}`}
        title={failure ?? `Delete ${title}`}
        className="grid size-7 place-items-center rounded-md text-muted transition-colors duration-150 hover:bg-elevated hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
      >
        <TrashIcon className="size-3.5" />
      </button>
      {failure ? (
        <span role="alert" className="sr-only">
          {failure}
        </span>
      ) : null}
    </span>
  );
}
