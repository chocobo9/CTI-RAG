"""CTI-RAG agent team — persistent teammate threads coordinating over a file-backed
MessageBus and a recoverable disk task board (learn-claude-code s09–s11 pattern).

NOT a subagent harness: every role is a long-lived thread with its own agent loop and a
drain-on-read JSONL inbox; coordination flows through the shared mailbox, and the
Phase C → Phase D hard gate is a pending → approved | rejected handshake persisted on disk.
"""
