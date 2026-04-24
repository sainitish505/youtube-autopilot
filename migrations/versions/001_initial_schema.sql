-- =============================================================================
-- 001_initial_schema.sql
-- YouTube Autopilot SaaS — Initial Database Schema
--
-- Run against Supabase PostgreSQL or a local postgres:16 instance.
-- Supabase: paste into the SQL Editor at app.supabase.com > SQL Editor
-- Local:    psql -U postgres -d youtube_saas -f 001_initial_schema.sql
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- user_profiles
-- Created automatically for every auth.users row via a trigger (Supabase),
-- or manually in local dev.
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id           UUID PRIMARY KEY,  -- matches auth.users.id in Supabase
    display_name TEXT,
    plan         TEXT NOT NULL DEFAULT 'free',   -- 'free' | 'pro' | 'enterprise'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE user_profiles IS 'Extended profile data for each registered user.';

-- =============================================================================
-- user_api_keys
-- Stores encrypted third-party API credentials per user.
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_api_keys (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                    UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    openai_api_key_enc         BYTEA,                    -- Fernet-encrypted
    youtube_refresh_token_enc  BYTEA,                    -- Fernet-encrypted
    youtube_channel_id         TEXT,
    youtube_channel_name       TEXT,
    youtube_connected_at       TIMESTAMPTZ,
    openai_added_at            TIMESTAMPTZ,
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_api_keys_user UNIQUE (user_id)
);

COMMENT ON TABLE user_api_keys IS 'Encrypted third-party API keys per user. Fernet-encrypted at the app layer.';
COMMENT ON COLUMN user_api_keys.openai_api_key_enc IS 'OpenAI API key, Fernet-encrypted. Never returned in plain text.';
COMMENT ON COLUMN user_api_keys.youtube_refresh_token_enc IS 'YouTube OAuth2 refresh token, Fernet-encrypted.';

-- =============================================================================
-- user_settings
-- Per-user pipeline and video preferences.
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_settings (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                    UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    autonomous_mode            BOOLEAN NOT NULL DEFAULT TRUE,
    max_video_minutes          INT     NOT NULL DEFAULT 10,
    default_niche              TEXT             DEFAULT '',
    tts_voice                  TEXT    NOT NULL DEFAULT 'alloy',
    upload_privacy             TEXT    NOT NULL DEFAULT 'public',  -- 'public'|'unlisted'|'private'
    video_model                TEXT    NOT NULL DEFAULT 'sora-2',
    auto_approve_under_dollars FLOAT   NOT NULL DEFAULT 2.0,
    CONSTRAINT uq_user_settings_user UNIQUE (user_id)
);

COMMENT ON TABLE user_settings IS 'Per-user pipeline preferences (voice, video length, privacy, etc.).';

-- =============================================================================
-- jobs
-- One row per video generation job.
-- =============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'queued',  -- queued|running|completed|failed|cancelled
    niche           TEXT,
    title           TEXT,
    scenes_count    INT,
    video_url       TEXT,           -- YouTube URL when upload succeeds
    r2_video_path   TEXT,           -- Cloudflare R2 object key
    total_cost_usd  FLOAT NOT NULL DEFAULT 0.0,
    error_message   TEXT,
    plan_json       JSONB,          -- Full VideoPlan JSON (for replay/debugging)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobs_user_id       ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status        ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at    ON jobs(created_at DESC);

COMMENT ON TABLE jobs IS 'One row per video generation job. status: queued → running → completed|failed.';

-- =============================================================================
-- job_agent_statuses
-- Per-agent progress tracking within a job.
-- =============================================================================
CREATE TABLE IF NOT EXISTS job_agent_statuses (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id     UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,         -- CEO | ScriptPolisher | VisualGenerator | ...
    status     TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_job_agent UNIQUE (job_id, agent_name)
);

CREATE INDEX IF NOT EXISTS idx_job_agent_statuses_job_id ON job_agent_statuses(job_id);

-- =============================================================================
-- job_assets
-- Generated artifacts (video clips, audio, images, thumbnails) stored on R2.
-- =============================================================================
CREATE TABLE IF NOT EXISTS job_assets (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id     UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    type       TEXT NOT NULL,         -- video_clip | audio | thumbnail | image
    r2_path    TEXT NOT NULL,         -- R2 object key: {user_id}/{job_id}/{filename}
    public_url TEXT,                  -- CDN URL for direct browser access
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_assets_job_id ON job_assets(job_id);

-- =============================================================================
-- analytics_events
-- Fine-grained API call tracking for per-user cost dashboards.
-- =============================================================================
CREATE TABLE IF NOT EXISTS analytics_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    job_id       UUID REFERENCES jobs(id) ON DELETE SET NULL,
    event_type   TEXT NOT NULL,       -- sora_generate | tts_generate | dalle_generate | gpt4o_call
    tokens_used  INT  NOT NULL DEFAULT 0,
    cost_usd     FLOAT NOT NULL DEFAULT 0.0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_user_id  ON analytics_events(user_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_job_id   ON analytics_events(job_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_created  ON analytics_events(created_at DESC);

-- =============================================================================
-- Row-Level Security (Supabase only — skip for local postgres)
--
-- Uncomment these when using Supabase:
-- =============================================================================
-- ALTER TABLE user_profiles      ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE user_api_keys      ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE user_settings      ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE jobs               ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE job_agent_statuses ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE job_assets         ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE analytics_events   ENABLE ROW LEVEL SECURITY;
--
-- CREATE POLICY "users see own profile"  ON user_profiles      FOR ALL USING (auth.uid() = id);
-- CREATE POLICY "users see own keys"     ON user_api_keys      FOR ALL USING (auth.uid() = user_id);
-- CREATE POLICY "users see own settings" ON user_settings      FOR ALL USING (auth.uid() = user_id);
-- CREATE POLICY "users see own jobs"     ON jobs               FOR ALL USING (auth.uid() = user_id);
-- CREATE POLICY "users see own statuses" ON job_agent_statuses FOR ALL USING (
--     job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid())
-- );
-- CREATE POLICY "users see own assets"   ON job_assets         FOR ALL USING (
--     job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid())
-- );
-- CREATE POLICY "users see own events"   ON analytics_events   FOR ALL USING (auth.uid() = user_id);

-- =============================================================================
-- Supabase trigger: auto-create user_profile on signup
-- (Only needed when using Supabase Auth — comment out for local dev)
-- =============================================================================
-- CREATE OR REPLACE FUNCTION public.handle_new_user()
-- RETURNS trigger AS $$
-- BEGIN
--   INSERT INTO public.user_profiles (id, display_name)
--   VALUES (new.id, new.raw_user_meta_data->>'display_name');
--   RETURN new;
-- END;
-- $$ LANGUAGE plpgsql SECURITY DEFINER;
--
-- DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
-- CREATE TRIGGER on_auth_user_created
--   AFTER INSERT ON auth.users
--   FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
