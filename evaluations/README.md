# Evaluations

Placeholder for Via's agent evaluation harness (v0.2). This directory will
hold prompt-regression and tool-quality evaluations so that changes to
prompts, models or tools are gated on measurable behavior - not vibes.

## Planned layout

```
evaluations/
├── cases/                  # one YAML per evaluation case
│   ├── metadata-qa.yaml    # question, expected tool calls, rubric
│   └── transcript-cite.yaml
├── runners/                # harness drivers executing cases against
│                           # LocalModelClient / Bedrock backends
└── reports/                # generated scorecards per git revision
```

## Case format (sketch)

```yaml
name: metadata-duration-question
prompt_version: video_assistant@1
model: local # or bedrock/<pegasus-id>
input:
  message: "How long is this video?"
  video_fixture: short-clip # seeded via packages/db fixtures
expect:
  tools_called: [get_video_metadata]
  answer_contains: ["duration"]
  max_citations: 1
```

## Principles

- **Deterministic first**: run against `LocalModelClient` in CI for wiring
  regressions; model-backed evals run on demand.
- **Versioned expectations**: each case pins the prompt version it tests so
  publishing a new prompt version is an explicit, reviewable event.
- **Trace-aware**: runners assert on recorded spans (tools called,
  authorization outcomes), not just final answers.
