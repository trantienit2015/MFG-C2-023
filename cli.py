"""AGENTIC STAR Marketplace entrypoint — one-shot Pod process.

Referenced by this repo's Dockerfile as the image `CMD`. Compiles the agent,
provisions its secrets, then hands off to shared.bootstrap.marketplace_app for
the Marketplace lifecycle (identity, input, events, terminal delivery, exit).

`config=` is not optional: without it every `self.config.get(...)` in the graph
and its nodes resolves to None, so config/config.yaml would be loaded by nobody
and the agent would silently run on hardcoded defaults.

`namespace=` here is the Marketplace secret-provisioning namespace — a separate
concept from config/agent.yaml's AgentRegistry `namespace:` key that happens to
share its value.
"""

from pathlib import Path

from framework.utils.config_loader import load_agent_config
from shared.bootstrap.marketplace_app import run_agent_marketplace

from src.graph.graph import ECRClassificationGraph

# Config overrides applied on top of config/config.yaml, without editing it.
extend_config = {}

if __name__ == "__main__":
    run_agent_marketplace(
        ECRClassificationGraph,
        agent_name="mfg-c2-023",
        namespace="mfg",
        config={**load_agent_config(Path(__file__).resolve().parent), **extend_config},
    )
