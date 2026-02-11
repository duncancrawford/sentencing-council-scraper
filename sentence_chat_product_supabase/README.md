# Sentence Chat Product (Supabase Edge)

This is a Supabase-specific rebuild of the `sentence_chat_product` APIs as
separate Edge Functions (one per API).

## API routes

Functions and URLs:

- `health`
  - `GET https://<project-ref>.supabase.co/functions/v1/health`
- `calculate-sentence`
  - `POST https://<project-ref>.supabase.co/functions/v1/calculate-sentence`
- `search-guidelines`
  - `POST https://<project-ref>.supabase.co/functions/v1/search-guidelines`
- `chat-turn`
  - `POST https://<project-ref>.supabase.co/functions/v1/chat-turn`

## Directory layout

- `openapi.json`
  - OpenAPI 3.1 spec for deployed Supabase function URLs
- `supabase/functions/health/index.ts`
- `supabase/functions/calculate-sentence/index.ts`
- `supabase/functions/search-guidelines/index.ts`
- `supabase/functions/chat-turn/index.ts`
- `supabase/functions/_shared/router.ts`
  - Shared implementation (validation, sentencing rules, retrieval, chat-turn
    orchestration)
- `supabase/sql/schema.sql`
  - Base database schema
- `supabase/sql/edge_rpcs.sql`
  - RPC helpers used by the Edge Functions

## Deploy

## 1) Apply SQL scripts in Supabase

Run in SQL editor (in order):

1. `/Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product_supabase/supabase/sql/schema.sql`
2. `/Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product_supabase/supabase/sql/edge_rpcs.sql`

## 2) Deploy Edge Functions

From repository root:

```bash
supabase functions deploy health --project-ref <project-ref> --no-verify-jwt
supabase functions deploy calculate-sentence --project-ref <project-ref> --no-verify-jwt
supabase functions deploy search-guidelines --project-ref <project-ref> --no-verify-jwt
supabase functions deploy chat-turn --project-ref <project-ref> --no-verify-jwt
```

## 3) Set function secrets

Required:

```bash
supabase secrets set SUPABASE_URL=https://<project-ref>.supabase.co
supabase secrets set SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
```

Optional (vector retrieval):

```bash
supabase secrets set OPENAI_API_KEY=<openai-key>
supabase secrets set OPENAI_EMBEDDING_MODEL=text-embedding-3-small
supabase secrets set ENABLE_VECTOR_SEARCH=true
supabase secrets set RETRIEVAL_TOP_K=6
```

## 4) Local development

```bash
supabase functions serve health --no-verify-jwt
supabase functions serve calculate-sentence --no-verify-jwt
supabase functions serve search-guidelines --no-verify-jwt
supabase functions serve chat-turn --no-verify-jwt
```

Test:

```bash
curl http://localhost:54321/functions/v1/health
```

## Notes

- Validation errors return HTTP `422` with a `detail` array.
- Calculation audit logging is best-effort and does not fail the request if
  audit insert fails.
- If `OPENAI_API_KEY` is unset, guideline retrieval uses text-only ranking.
