# ChatGPT Actions Setup

Use the FastAPI OpenAPI spec exposed by this service for ChatGPT Actions.

## Base URL

- Local: `http://localhost:8010`
- Production: your deployed API URL

## OpenAPI URL

- `GET /openapi.json`

## Recommended Actions to expose

- `POST /v1/calculate_sentence`
- `POST /v1/search_guidelines`

Optional:
- `POST /v1/chat_turn` (single endpoint orchestration)

## Instruction pattern for GPT

Use this policy in your GPT system instructions:

1. Ask for missing sentencing facts first (offence, dates, age, plea stage, sentence type, term/fine).
2. Call `calculate_sentence` for deterministic output.
3. Call `search_guidelines` using the user question and `offence_id`.
4. Answer with:
   - sentence result,
   - uncertainty warnings,
   - citation URLs.

## Suggested safety constraints

- Always display a legal disclaimer and state this is decision support, not legal advice.
- If critical facts are missing, do not guess; ask follow-up questions.
- If warnings include mandatory-life or dangerousness triggers, surface them prominently.

