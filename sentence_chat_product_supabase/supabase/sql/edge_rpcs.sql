-- RPC helpers for the sentence-chat Supabase Edge Functions.
-- Apply after the base schema in src/sentence_chat_product/db/schema.sql

create or replace function api_fetch_offence_by_id(p_offence_id uuid)
returns table (
  offence_id uuid,
  canonical_name text,
  short_name text,
  offence_category text,
  provision text,
  guideline_url text,
  legislation_url text,
  maximum_sentence_type text,
  maximum_sentence_amount text,
  minimum_sentence_code text,
  specified_violent boolean,
  specified_sexual boolean,
  specified_terrorist boolean,
  listed_offence boolean,
  schedule18a_offence boolean,
  schedule19za boolean,
  cta_notification boolean
)
language sql
stable
as $$
  select
    offence_id,
    canonical_name,
    short_name,
    offence_category,
    provision,
    guideline_url,
    legislation_url,
    maximum_sentence_type,
    maximum_sentence_amount,
    minimum_sentence_code,
    specified_violent,
    specified_sexual,
    specified_terrorist,
    listed_offence,
    schedule18a_offence,
    schedule19za,
    cta_notification
  from offence_catalog
  where offence_id = p_offence_id;
$$;

create or replace function api_search_offences(p_query text, p_limit integer default 5)
returns table (
  offence_id uuid,
  canonical_name text,
  short_name text,
  offence_category text,
  provision text,
  guideline_url text,
  legislation_url text,
  maximum_sentence_type text,
  maximum_sentence_amount text,
  minimum_sentence_code text,
  specified_violent boolean,
  specified_sexual boolean,
  specified_terrorist boolean,
  listed_offence boolean,
  schedule18a_offence boolean,
  schedule19za boolean,
  cta_notification boolean,
  score real
)
language sql
stable
as $$
  select
    oc.offence_id,
    oc.canonical_name,
    oc.short_name,
    oc.offence_category,
    oc.provision,
    oc.guideline_url,
    oc.legislation_url,
    oc.maximum_sentence_type,
    oc.maximum_sentence_amount,
    oc.minimum_sentence_code,
    oc.specified_violent,
    oc.specified_sexual,
    oc.specified_terrorist,
    oc.listed_offence,
    oc.schedule18a_offence,
    oc.schedule19za,
    oc.cta_notification,
    greatest(
      similarity(oc.canonical_name, p_query),
      similarity(coalesce(oc.short_name, ''), p_query),
      similarity(coalesce(oc.provision, ''), p_query)
    )::real as score
  from offence_catalog oc
  order by score desc, canonical_name asc
  limit p_limit;
$$;

create or replace function api_fetch_sentencing_matrix(p_offence_id uuid)
returns table (
  matrix_id text,
  guideline_id text,
  offence_id text,
  culpability text,
  harm text,
  starting_point_text text,
  category_range_text text
)
language sql
stable
as $$
  select distinct on (sm.matrix_id)
    sm.matrix_id::text,
    sm.guideline_id::text,
    sm.offence_id::text,
    sm.culpability,
    sm.harm,
    sm.starting_point_text,
    sm.category_range_text
  from sentencing_matrix sm
  left join offence_guideline_links ogl
    on ogl.guideline_id = sm.guideline_id
  where sm.offence_id = p_offence_id
     or ogl.offence_id = p_offence_id
  order by sm.matrix_id, sm.guideline_id;
$$;

create or replace function api_search_guideline_chunks_text(
  p_query text,
  p_top_k integer,
  p_offence_id uuid default null
)
returns table (
  chunk_id text,
  guideline_id text,
  offence_id text,
  section_type text,
  section_heading text,
  chunk_text text,
  source_url text,
  score real
)
language sql
stable
as $$
  select
    gc.chunk_id::text,
    gc.guideline_id::text,
    gc.offence_id::text,
    gc.section_type,
    gc.section_heading,
    gc.chunk_text,
    gc.source_url,
    ts_rank_cd(gc.tsv, plainto_tsquery('english', p_query))::real as score
  from guideline_chunks gc
  where (
    p_offence_id is null
    or gc.offence_id = p_offence_id
    or gc.guideline_id in (
      select guideline_id from offence_guideline_links where offence_id = p_offence_id
    )
  )
  order by score desc, similarity(gc.chunk_text, p_query) desc
  limit p_top_k;
$$;

create or replace function api_search_guideline_chunks_hybrid(
  p_query text,
  p_query_embedding vector(1536),
  p_top_k integer,
  p_offence_id uuid default null
)
returns table (
  chunk_id text,
  guideline_id text,
  offence_id text,
  section_type text,
  section_heading text,
  chunk_text text,
  source_url text,
  vector_score real,
  text_score real,
  score real
)
language sql
stable
as $$
  select
    gc.chunk_id::text,
    gc.guideline_id::text,
    gc.offence_id::text,
    gc.section_type,
    gc.section_heading,
    gc.chunk_text,
    gc.source_url,
    coalesce(1 - (gc.embedding <=> p_query_embedding), 0)::real as vector_score,
    ts_rank_cd(gc.tsv, plainto_tsquery('english', p_query))::real as text_score,
    (
      coalesce(1 - (gc.embedding <=> p_query_embedding), 0) * 0.75
      + ts_rank_cd(gc.tsv, plainto_tsquery('english', p_query)) * 0.25
    )::real as score
  from guideline_chunks gc
  where (
    p_offence_id is null
    or gc.offence_id = p_offence_id
    or gc.guideline_id in (
      select guideline_id from offence_guideline_links where offence_id = p_offence_id
    )
  )
  order by score desc
  limit p_top_k;
$$;

create or replace function api_store_calculation_audit(
  p_offence_id uuid,
  p_request_payload jsonb,
  p_result_payload jsonb
)
returns void
language sql
volatile
as $$
  insert into calculation_audit (offence_id, request_payload, result_payload)
  values (p_offence_id, p_request_payload, p_result_payload);
$$;
