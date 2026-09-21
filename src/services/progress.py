"""AgentCore Platform v1.0"""

# Progress reporting for the Marketplace chat.
#
# Pod cold start reaches ~10 minutes; without progress events the chat is
# blank for that whole window and reads as a hung agent. Outside Marketplace
# `emitter()` is a NullEventEmitter (no-op), so these calls are safe in tests
# and in the standalone server path.
#
# Fail-soft by design: progress is cosmetic and must never break a run. The
# helper is intentionally in its own module (never calling itself) — a helper
# that wrapped its own call site would recurse, and the `except` below would
# hide the RecursionError while emitting nothing at all.
#
# Nodes MUST NOT emit terminal events (COMPLETION_*) — that is the runner's
# responsibility. Payloads carry stage/count metadata only, never caller content.

from typing import Any
import logging

logger = logging.getLogger(__name__)


def emit_progress(message: str, stage: str, **metadata: Any) -> None:
    """Emit one PROGRESS_UPDATE event; silently do nothing if unavailable."""
    try:
        from shared.services.events import emitter
        from shared.services.events.types import EventType

        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message=message,
            metadata={"stage": stage, **metadata},
        )
    except Exception:  # noqa: BLE001 - progress is cosmetic; never fail a run for it
        logger.debug("progress emit unavailable for stage=%s", stage, exc_info=True)
