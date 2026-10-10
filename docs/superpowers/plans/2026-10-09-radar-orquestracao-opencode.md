# Radar de Concursos Multiagent OpenCode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Follow the active session's delegation instructions; never delegate solely because this header recommends it.

**Goal:** Configure a project-local, persistent OpenCode orchestrator and four specialists, then prove a safe, real delegation from a fresh process.

**Architecture:** Use native OpenCode project config, Markdown agents, and `task` delegation. Shared governance lives in `AGENTS.md`; each agent holds only its role and permissions. The central agent builds task-specific prompts and verifies actual files/tests rather than trusting agent reports. No custom plugin or product implementation.

**Tech Stack:** OpenCode CLI 1.18.35, JSON config, Markdown/YAML frontmatter, PowerShell 7+, Git for Windows, Superpowers plugin already installed globally.

**Spec:** `docs/superpowers/specs/2026-10-09-radar-orquestracao-opencode-design.md`

## Global Constraints

- Location: `C:\Users\anton\OneDrive\Desktop\radar-de-concursos`; use PowerShell and preserve global `C:\Users\anton\.config\opencode\opencode.jsonc` untouched.
- No product feature, remote Git repository, push, automatic merge to `main`, production publication, destructive migration, credential exposure, or unsanctioned paid external operation.
- No commit without an explicit user request; this overrides skill examples recommending frequent commits. Initialize only local Git when safe.
- Verify exact models with `opencode models inferhub`, load project agents from a fresh CLI process, and distinguish catalog listing from successful model invocation.
- Each prompt includes the 14 task-specific fields in the spec; immutable domain rules remain in `AGENTS.md`.
- Do not spawn subagents for implementing this configuration unless the user's applicable instructions explicitly authorize it. The user has explicitly requested a controlled delegation test; conduct that test after configuration is loaded.

## Review Focus

1. Existing content appears in the destination before Git initialization: preserve it and inspect `git status`/repository ancestry; Task 1 confirms no overwrite and no automatic commit.
2. A previously configured global permission or provider overrides local expectations: Task 2 checks actual agent resolution and effective task permissions without dumping credentials.
3. Invalid Markdown frontmatter, model ID, or JSON config prevents CLI startup: Task 2 loads all agents in a new process; resolve and retry only local files.
4. An agent claims a document was read but no `task` invocation occurred: Task 3 requires JSON tool-call evidence and compares returned facts to the document.
5. The selected model is listed but its endpoint fails: Task 3 records error, uses a listed alternate only after validation, and does not claim route success without a response.

---

## File map

- `opencode.json`: `$schema`, local default agent, and only essential project settings. Preserve provider credentials in global config.
- `AGENTS.md`: shared project intent, domain invariants, scope/approval boundaries, and instruction precedence.
- `.opencode/agents/orquestrador.md`: primary agent, prompt generation and delegation/review workflow.
- `.opencode/agents/backend.md`: backend boundaries and contract/test requirements.
- `.opencode/agents/collectors.md`: official sources, provenance, fault isolation, fixtures and safe retries.
- `.opencode/agents/frontend.md`: UI boundaries, API contract, empty/loading/error states.
- `.opencode/agents/qa.md`: independent evidence-based review and default read-only posture.
- `docs/AGENT_MODELS.md`: chosen IDs, alternative routes, listing vs. invocation evidence.
- `docs/AGENT_WORKFLOW.md`: delegation lifecycle, prompt field checklist, isolation, review and failure handling.
- `docs/OPENCODE_SUPERPOWERS.md`: installed plugin and available skills, operational rules and verification.
- `README.md`: verified PowerShell startup and diagnostics commands.
- `.gitignore`: local artifacts and credentials, without hiding project configuration.
- `docs/DELEGATION_PROBE.md`: short non-secret factual test document for a read-only subagent probe.

### Task 1: Prepare safe project governance and Git baseline

**Files:** Create `.gitignore`, `AGENTS.md`, `docs/DELEGATION_PROBE.md`; inspect existing spec in `docs/superpowers/specs/`. Git metadata created in repository root only if no existing repository.

**Interfaces:** Produces a stable `docs/DELEGATION_PROBE.md` with two factual sentences, used by Task 3 to check returned summary; `AGENTS.md` is read by every agent.

- [ ] **Step 1: Re-inspect root and ancestry.** From the root run `git rev-parse --show-toplevel` and `git status --short --branch`; list root contents with the dedicated directory reader. If the folder or spec unexpectedly changed, inspect before creating anything. Confirm `Test-Path -LiteralPath 'C:\Users\anton\OneDrive\Desktop\radar-de-concursos'` returns `True`.
- [ ] **Step 2: Create `.gitignore`** using a patch, containing at least `.env`, `.env.*` with an exception for `.env.example`, `__pycache__/`, `.pytest_cache/`, `node_modules/`, `.venv/`, `dist/`, `build/`, and `*.log`. Do not ignore `.opencode/` or docs.
- [ ] **Step 3: Create `AGENTS.md`** with project purpose, all critical domain distinctions from the spec, instruction precedence, current phase (configuration only), scope/no-secrets/no-push/no-merge safety, and proof-based completion. Add `docs/DELEGATION_PROBE.md` containing exactly these checkable facts: `Nesta fase, configuramos agentes do OpenCode; não coletamos editais.` and `A validação mínima é uma delegação real de leitura de documentação.`
- [ ] **Step 4: Verify before initializing Git.** Read both resulting files. If `git rev-parse --show-toplevel` failed because the root is unversioned, run `git init` in the project root (no remote); if already under an existing repository, inspect and preserve that repository rather than nesting another one. Run `git status --short --branch` and `git remote -v`; expected no remote and only intended untracked files. Never stage credentials or commit.

### Task 2: Configure persistent agents and operating documents

**Files:** Create `opencode.json`, `.opencode/agents/{orquestrador,backend,collectors,frontend,qa}.md`, `docs/{AGENT_MODELS,AGENT_WORKFLOW,OPENCODE_SUPERPOWERS}.md`, `README.md`.

**Interfaces:** Consumes Task 1 `AGENTS.md`; produces `default_agent` named `orquestrador` and four distinct `mode: subagent` agents callable by `task`. Task 3 consumes the named QA agent and probe document.

- [ ] **Step 1: Check current config references.** Use Context7 official OpenCode docs already resolved as `/anomalyco/opencode` for Markdown frontmatter/permissions. Check `https://opencode.ai/config.json` if any exact field is uncertain. Run `opencode models inferhub` filtered in-memory to the selected IDs, without printing provider credentials. Use `opencode debug skill` for installed skills if needed; do not dump global resolved config into the report.
- [ ] **Step 2: Create `opencode.json`** with `"$schema": "https://opencode.ai/config.json"` and `"default_agent": "orquestrador"`; add only additional fields verified necessary on OpenCode 1.18.35. Configure `inferhub/cb/gpt-5.5` in the primary Markdown agent, not globally. Never paste keys or MCP configuration.
- [ ] **Step 3: Create `.opencode/agents/orquestrador.md`.** Frontmatter: `description`, `mode: primary`, `model: inferhub/cb/gpt-5.5`, task permissions allowing `backend`, `collectors`, `frontend`, `qa` after default-deny, with pattern order checked against schema. Body: inspect/plan/skills; write unique prompts containing ID, goal, context, files, diagnosis, responsibility, allowed/prohibited scope, dependencies/contracts, domain, skills, tests, acceptance, report and stop criteria; invoke `task` for actual tasks; inspect returned changes, test and request corrections; avoid indiscriminate delegation and serialize shared-file writes.
- [ ] **Step 4: Create four specialist Markdown definitions.** Use only listed model IDs: backend `inferhub/cbcn/deepseek-v4-pro`, collectors `inferhub/cb/deepseek-v4.1-flash`, frontend `inferhub/ali/deepseek-v4-pro-0813`, QA `inferhub/cb/glm-5.3` (a different model family from the implementers). Each `mode: subagent`; deny further `task` dispatch; QA `permission.edit: deny` for default read-only probe; other restrictions grounded in effective OpenCode permissions. Include explicit conditional stack, scoped write boundaries, evidence and tests. If route validation changes an ID, update docs and config together.
- [ ] **Step 5: Write focused docs.** `docs/AGENT_MODELS.md` records IDs and whether listed/invoked; `docs/AGENT_WORKFLOW.md` documents the 14 prompt fields, task sequencing, isolation, verification/correction and meaningful QA independence; `docs/OPENCODE_SUPERPOWERS.md` records real installed plugin/skills, skill invocation in individual sessions and limitations. `README.md` gives verified commands such as `opencode 'C:\Users\anton\OneDrive\Desktop\radar-de-concursos'`, `opencode agent list`, `opencode debug agent orquestrador`, and `opencode run --agent orquestrador '...'` with working-directory guidance. Mark unrun route tests as unverified.
- [ ] **Step 6: Validate from project root with new CLI processes.** Run `opencode agent list` and inspect existence/modes of all five without echoing huge permission dumps. Run `opencode debug agent orquestrador` with a targeted safe view of task rules and model (avoid logging secrets). Run `opencode run --help` and verify CLI command shape. Read back every new file. If parser rejects a local field, inspect schema/error and change only local config; rerun until CLI loads. Verify `git status --short --branch` shows only intended files.

### Task 3: Prove a controlled real delegation and record results

**Files:** Modify `docs/AGENT_MODELS.md`, `docs/AGENT_WORKFLOW.md`, `README.md` only if required by observed outcome; do not edit the probe facts after delegation.

**Interfaces:** Consumes `orquestrador` and `qa` agent definitions and Task 1 `docs/DELEGATION_PROBE.md`. Produces a factual verification record in `docs/AGENT_WORKFLOW.md`: exact invocation, evidence of `task`, result, permission/model limitations and reproduction command.

- [ ] **Step 1: Establish baseline.** Read `docs/DELEGATION_PROBE.md`, `opencode.json`, agent headers, and Git status. Start a fresh process from project root. Ask primary agent explicitly: `Delegue ao agente qa via task uma leitura somente de docs/DELEGATION_PROBE.md. Peça duas afirmações factuais, o arquivo lido e problemas encontrados. Não edite arquivos. Retorne a resposta e evidencie a chamada task.` Use documented `opencode run --agent orquestrador --format json '...'` (confirm flags with `opencode run --help`).
- [ ] **Step 2: Verify tool evidence.** Inspect JSON event types and locate a real tool call with name `task`, target `qa`, and tool completion; compare subagent response against the two exact probe sentences. If no task event, count as failed even if the prose looks correct. Do not print secrets or paste raw event payloads into documentation; record only safe event IDs/names and response facts. Check whether the subagent actually read the local file, rather than repeating the user prompt.
- [ ] **Step 3: Diagnose only observed failures.** If default model route rejects request, test a listed compatible alternative with a short harmless CLI prompt, then update primary model only on confirmed route success; similarly update QA if needed. If permission blocks dispatch, inspect effective rules and fix only project files. Limit retries to observed root causes and do not claim untested routes work. If CLI cannot produce inspectable tool events, mark delegation `não verificada` with reproduction steps.
- [ ] **Step 4: Record final evidence.** In docs distinguish models merely cataloged from models invoked, task tool event observed/not observed, summary correctness, needed permissions, and any error. Run `opencode agent list` and `git status --short --branch` once more; read final edited files, check only intended paths changed and `.gitignore` excludes `.env`. No merge, push or commit. Present final report grouped by diagnosis, files, agents, orchestration, verified PowerShell commands, tests, and remaining limitations.
