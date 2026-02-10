-- Sentence Chat Product schema
-- Apply in Supabase SQL editor or psql before loading ETL output.

create extension if not exists pgcrypto;
create extension if not exists vector;
create extension if not exists pg_trgm;

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create table if not exists source_versions (
  source_version_id uuid primary key default gen_random_uuid(),
  source_name text not null,
  source_path text not null,
  source_hash text not null,
  metadata jsonb not null default '{}'::jsonb,
  loaded_at timestamptz not null default now()
);

create table if not exists offence_catalog (
  offence_id uuid primary key,
  canonical_name text not null,
  short_name text not null,
  offence_category text,
  provision text,
  guideline_url text,
  legislation_url text,
  maximum_sentence_type text,
  maximum_sentence_amount text,
  minimum_sentence_code text not null default '',
  specified_violent boolean not null default false,
  specified_sexual boolean not null default false,
  specified_terrorist boolean not null default false,
  listed_offence boolean not null default false,
  schedule18a_offence boolean not null default false,
  schedule19za boolean not null default false,
  cta_notification boolean not null default false,
  shpo boolean not null default false,
  disqualification boolean not null default false,
  safeguarding1 boolean not null default false,
  safeguarding2 boolean not null default false,
  safeguarding3 boolean not null default false,
  safeguarding4 boolean not null default false,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_offence_catalog_updated_at on offence_catalog;
create trigger trg_offence_catalog_updated_at
before update on offence_catalog
for each row execute procedure set_updated_at();

create index if not exists idx_offence_catalog_canonical_name_trgm
  on offence_catalog using gin (canonical_name gin_trgm_ops);
create index if not exists idx_offence_catalog_provision_trgm
  on offence_catalog using gin (provision gin_trgm_ops);

create table if not exists guidelines (
  guideline_id uuid primary key,
  slug text not null unique,
  offence_name text not null,
  url text not null unique,
  court_type text,
  category text,
  source_tab text,
  effective_from text,
  legislation_text text,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_guidelines_updated_at on guidelines;
create trigger trg_guidelines_updated_at
before update on guidelines
for each row execute procedure set_updated_at();

create index if not exists idx_guidelines_offence_name_trgm
  on guidelines using gin (offence_name gin_trgm_ops);

create table if not exists offence_guideline_links (
  link_id uuid primary key,
  offence_id uuid not null references offence_catalog(offence_id) on delete cascade,
  guideline_id uuid not null references guidelines(guideline_id) on delete cascade,
  match_method text not null,
  match_confidence numeric(5,4) not null,
  is_primary boolean not null default true,
  created_at timestamptz not null default now(),
  unique (offence_id, guideline_id)
);

create index if not exists idx_offence_guideline_links_offence on offence_guideline_links(offence_id);
create index if not exists idx_offence_guideline_links_guideline on offence_guideline_links(guideline_id);

create table if not exists sentencing_matrix (
  matrix_id uuid primary key,
  guideline_id uuid not null references guidelines(guideline_id) on delete cascade,
  offence_id uuid references offence_catalog(offence_id) on delete set null,
  culpability text,
  harm text,
  starting_point_text text,
  category_range_text text,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_sentencing_matrix_guideline on sentencing_matrix(guideline_id);
create index if not exists idx_sentencing_matrix_offence on sentencing_matrix(offence_id);

create table if not exists guideline_factors (
  factor_id uuid primary key,
  guideline_id uuid not null references guidelines(guideline_id) on delete cascade,
  offence_id uuid references offence_catalog(offence_id) on delete set null,
  factor_type text not null,
  factor_text text not null,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_guideline_factors_guideline on guideline_factors(guideline_id);
create index if not exists idx_guideline_factors_offence on guideline_factors(offence_id);
create index if not exists idx_guideline_factors_type on guideline_factors(factor_type);

create table if not exists guideline_chunks (
  chunk_id uuid primary key,
  guideline_id uuid not null references guidelines(guideline_id) on delete cascade,
  offence_id uuid references offence_catalog(offence_id) on delete set null,
  section_type text,
  section_heading text,
  chunk_index integer not null,
  chunk_text text not null,
  token_estimate integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  source_url text,
  embedding vector(1536),
  tsv tsvector generated always as (
    to_tsvector('english', coalesce(section_heading, '') || ' ' || coalesce(chunk_text, ''))
  ) stored,
  created_at timestamptz not null default now(),
  unique (guideline_id, section_type, chunk_index)
);

create index if not exists idx_guideline_chunks_guideline on guideline_chunks(guideline_id);
create index if not exists idx_guideline_chunks_offence on guideline_chunks(offence_id);
create index if not exists idx_guideline_chunks_tsv on guideline_chunks using gin(tsv);
create index if not exists idx_guideline_chunks_embedding_cos
  on guideline_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create table if not exists calculation_audit (
  audit_id uuid primary key default gen_random_uuid(),
  offence_id uuid references offence_catalog(offence_id) on delete set null,
  request_payload jsonb not null,
  result_payload jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_calculation_audit_offence on calculation_audit(offence_id);
create index if not exists idx_calculation_audit_created_at on calculation_audit(created_at desc);
