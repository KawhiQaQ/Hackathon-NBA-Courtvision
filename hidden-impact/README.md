# HiAgent engine

See the [project README](../README.md) for the demo and quick start, [setup guide](../docs/setup.md) for a fresh installation, and [AWS deployment guide](../docs/aws.md) for hosting your own workspace.

| Directory | Purpose |
| --- | --- |
| `cloud/api/` | Perception, scoring, Reviewer, rendering and HTTP worker |
| `cloud/agent/` | AgentCore entry point and model-side modules |
| `web/` | Upload workspace, video viewer, story frames and dashboard |
| `scripts/` | Local analysis, model preparation, deployment and export |
| `infra/` | AWS CDK application and pinned Node dependencies |
| `tests/` | Unit, contract, rendering and browser-logic regressions |
| `data/`, `prototypes/` | Historical experiments and source-bound reference records |

Schema identifiers retain the `hidden-impact/` namespace for compatibility. `.team-access-code` and `X-Team-Key` are retained as internal authentication names; they no longer depend on an event account.
