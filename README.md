# MFG-C2-023 — ECR Classification & Impact Assessment Agent

> **Category**: Cat 2 (orchestrates several steps to complete one specific job, rather than offering a single generic capability)
> **Industry**: MFG (manufacturing)

## Overview

An Engineering Change Request (ECR) is a proposal to change a part, a material, a process
or a supplier on a product that is already designed — often already in production. Someone
has to decide how far-reaching the change is, what else it touches, what re-qualification
it triggers, and how long the review will take. This template does that first pass.

You give it an ECR document. It extracts the change metadata, classifies the impact as
safety-critical, major, minor or administrative against quality-management and production
part approval criteria, recommends a part-approval submission level, lists the downstream
parts, processes and suppliers the change reaches, and estimates the review lead time from
a rule table. Safety and advisory notices are attached to the result and cannot be
suppressed by configuration.

The structured input path is the primary one: supply the ECR as a JSON document with the
affected parts, processes and suppliers as fields, and those entities are carried through
to the downstream-impact list. A plain-text document is also accepted, but the text branch
performs only a best-effort extraction and does not detect entities — adapt that branch to
your own document structure if free text is your main input.

One caveat worth knowing before you rely on the output: the platform's input security gate
masks anything it reads as a personal name, and a two-word supplier name looks like one to
it. Such a supplier is counted and listed, but its name appears masked in the report. The
classification, approval level and lead time are unaffected, since those derive from the
change description and the rule tables.

The output is advisory throughout. The recommended approval level in particular is a
starting point for a quality engineer, not a binding decision, and the agent says so in
every report it produces.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and operational documentation
```

See `docs/` for the proposal, design, test specification, release notes and operation guide.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the knowledge sources and sample data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.

---

