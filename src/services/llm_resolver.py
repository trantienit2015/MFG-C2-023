"""AgentCore Platform v1.0"""

# MFG-C2-023 — lazy Azure OpenAI resolution shared by the two LLM-backed inner
# nodes (impact_classify, ppap_recommend).
#
# Why this is not done in __init__: secrets are provisioned AFTER
# register_nodes() has already constructed every node , so an
# authenticated client cannot exist at construction time. It is resolved fresh
# on each execute() call and never cached on the node instance — node objects
# are shared across invocations and §9 forbids mutable instance state.

from typing import Any
import logging

from framework.schemas.agent_state import AgentState
from framework.schemas.invocation_context import InvocationContext

logger = logging.getLogger(__name__)

# Distinguishes "no llm key in config at all" (resolve one from ctx.secrets)
# from "llm=None passed explicitly" (deterministic opt-out). config.get("llm")
# returns None for a missing key, so a bare None cannot express both — and a
# deployment whose config.yaml omits `llm` would never call the LLM.
_UNSET = object()

_REQUIRED_SECRETS = ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT")


def resolve_llm(configured: Any, state: AgentState) -> Any:
    """Return the LLM client for this invocation, or None to stay deterministic."""
    if configured is not _UNSET:
        return configured  # includes an explicit None = caller opted out
    try:
        ctx = InvocationContext.from_state(state)
        api_key, endpoint, deployment = (ctx.secrets.require(k) for k in _REQUIRED_SECRETS)
    except Exception as exc:  # noqa: BLE001 — a credential-less deployment is valid
        logger.info("no Azure OpenAI credentials available, staying deterministic: %s", exc.__class__.__name__)
        return None
    # Lazy import: AzureOpenAIClient ships in the deployed wheel only, and a
    # module-scope import breaks local collection against an older wheel.
    from shared.services.llm.azure_openai_client import AzureOpenAIClient

    return AzureOpenAIClient(
        {
            "api_key": api_key,
            "azure_endpoint": endpoint,  # bare resource endpoint — the client rejects an API path
            "azure_deployment": deployment,
        }
    )
