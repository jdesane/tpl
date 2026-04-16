-- Region 1 Compliance Pipeline Tracker
-- Run once in the Supabase SQL Editor against a fresh project.

create table if not exists public.compliance_entries (
  id              uuid primary key default gen_random_uuid(),
  entry_date      date not null,
  time_block      text not null check (time_block in ('AM','PM')),
  rush_3day       integer default 0,
  rush_today      integer default 0,
  rush_tomorrow   integer default 0,
  rush_next_day   integer default 0,
  funds_in        integer default 0,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now(),
  unique (entry_date, time_block)
);

create index if not exists idx_compliance_entry_date
  on public.compliance_entries (entry_date desc);

-- Keep updated_at fresh on every update
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_compliance_entries_updated_at on public.compliance_entries;
create trigger trg_compliance_entries_updated_at
  before update on public.compliance_entries
  for each row execute function public.set_updated_at();

-- RLS: single-user internal tool, permissive anon policy.
alter table public.compliance_entries enable row level security;

drop policy if exists "anon all" on public.compliance_entries;
create policy "anon all" on public.compliance_entries
  for all to anon using (true) with check (true);
