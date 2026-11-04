"""Chat budgets and fixed copy.

These are code constants, not environment variables: they shape the prompt and
the answer, and changing them does not require a migration.
"""

CHAT_TOP_K = 8
CHAT_CONTEXT_CHARS = 12_000
CHAT_HISTORY_MESSAGES = 6
CHAT_HISTORY_CHARS = 6_000
CHAT_MAX_OUTPUT_TOKENS = 1_024
CHAT_TEMPERATURE = 0.2
CHAT_EXCERPT_CHARS = 320
CHAT_TITLE_CHARS = 80

DEFAULT_TITLE = "New conversation"
NO_CONTEXT_REPLY = "I couldn't find an answer to that in this workspace's documents."
