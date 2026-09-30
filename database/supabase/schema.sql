-- Optional Supabase tables for NyayaSearch AI application data.
-- Do not store the ChromaDB vector corpus here.

create table if not exists public.search_history (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    query text not null,
    filters jsonb default '{}'::jsonb,
    result_count int default 0,
    created_at timestamptz default now()
);

create table if not exists public.bookmarks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    case_id text not null,
    case_name text default '',
    created_at timestamptz default now(),
    unique (user_id, case_id)
);

create table if not exists public.feedback (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    query text default '',
    rating text not null,
    comment text default '',
    created_at timestamptz default now()
);

alter table public.search_history enable row level security;
alter table public.bookmarks enable row level security;
alter table public.feedback enable row level security;
