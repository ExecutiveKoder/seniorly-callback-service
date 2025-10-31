-- ============================================
-- SENIOR HEALTH ANALYTICS DATABASE SCHEMA
-- PostgreSQL
-- ============================================

-- Table 1: Senior Vitals (flexible, handles sparse data)
CREATE TABLE IF NOT EXISTS senior_vitals (
    id BIGSERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    vital_type VARCHAR(50) NOT NULL,
    -- Examples: 'bp_systolic', 'bp_diastolic', 'heart_rate', 'weight',
    --           'blood_sugar', 'sleep_hours', 'pain_level', 'temperature'
    vital_value DECIMAL(10,2) NOT NULL,
    unit VARCHAR(20) NOT NULL, -- 'mmHg', 'bpm', 'lbs', 'hours', 'scale', 'mg/dL'
    source VARCHAR(50) DEFAULT 'call', -- 'call', 'device', 'manual', 'self_reported'
    session_id VARCHAR(50), -- Link back to conversation session
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_senior_date ON senior_vitals(senior_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_vital_type ON senior_vitals(vital_type, recorded_at);
CREATE INDEX IF NOT EXISTS idx_session ON senior_vitals(session_id);

-- Table 2: Cognitive Assessments (daily cognitive health scores)
CREATE TABLE IF NOT EXISTS cognitive_assessments (
    id BIGSERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    assessment_date TIMESTAMP NOT NULL,

    -- Cognitive scores (nullable - not all assessed every day)
    memory_score INT, -- 0-100 scale
    orientation_score INT, -- 0-100 scale (time, place, person)
    language_score INT, -- 0-100 scale (word recall, fluency)
    executive_function_score INT, -- 0-100 scale (planning, reasoning)

    -- Conversation analysis
    coherence_score DECIMAL(5,2), -- 0-1 scale (how coherent was conversation)
    response_time_avg DECIMAL(6,2), -- Average response time in seconds
    topic_drift_count INT, -- Number of times lost track of conversation
    repetition_count INT, -- Repeated same information

    -- Overall
    overall_score INT, -- 0-100 composite score
    notes TEXT,
    session_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cog_senior_date ON cognitive_assessments(senior_id, assessment_date);
CREATE INDEX IF NOT EXISTS idx_cog_overall_score ON cognitive_assessments(overall_score, assessment_date);

-- Table 3: Call Summary (daily call overview)
CREATE TABLE IF NOT EXISTS call_summary (
    id BIGSERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    call_date TIMESTAMP NOT NULL,
    session_id VARCHAR(50) NOT NULL,

    -- Call details
    call_duration INT, -- seconds
    call_completed BOOLEAN NOT NULL DEFAULT true,
    call_answered BOOLEAN NOT NULL DEFAULT true,

    -- Wellness scores (1-10 scale)
    overall_wellness INT, -- Nullable if not assessed
    physical_health INT,
    mental_health INT,
    social_engagement INT,

    -- Specific checks
    medication_adherence BOOLEAN, -- NULL if not asked/answered
    medication_missed_count INT DEFAULT 0,

    -- Sentiment analysis
    mood_sentiment DECIMAL(5,2), -- -1 (very negative) to 1 (very positive)
    engagement_level INT, -- 0-10 scale

    -- Alerts and concerns
    red_flags_count INT DEFAULT 0,
    red_flags TEXT, -- JSON array of alert types

    -- AI-generated summary
    summary_text TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_call_senior_date ON call_summary(senior_id, call_date);
CREATE INDEX IF NOT EXISTS idx_call_session ON call_summary(session_id);
CREATE INDEX IF NOT EXISTS idx_call_red_flags ON call_summary(red_flags_count, call_date);

-- Table 4: Health Alerts (track concerning patterns)
CREATE TABLE IF NOT EXISTS health_alerts (
    id BIGSERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    alert_date TIMESTAMP NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    -- Examples: 'vital_abnormal', 'cognitive_decline', 'missed_medication',
    --           'isolation_detected', 'fall_risk', 'medication_side_effect'
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    description TEXT NOT NULL,

    -- Supporting data
    related_session_id VARCHAR(50),
    related_vital_id BIGINT,
    related_metric_value DECIMAL(10,2),

    -- Resolution tracking
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(100), -- caregiver name or system
    resolution_notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_senior_date ON health_alerts(senior_id, alert_date);
CREATE INDEX IF NOT EXISTS idx_alert_severity ON health_alerts(severity, alert_date);
CREATE INDEX IF NOT EXISTS idx_alert_unresolved ON health_alerts(resolved, alert_date);

-- Table 5: Medication Adherence Log
CREATE TABLE IF NOT EXISTS medication_adherence (
    id BIGSERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    log_date DATE NOT NULL,

    medications_taken BOOLEAN, -- Overall adherence
    medications_missed_count INT DEFAULT 0,
    specific_medications TEXT, -- JSON array of medications discussed

    side_effects_reported BOOLEAN DEFAULT false,
    side_effects_description TEXT,

    session_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(senior_id, log_date) -- One record per senior per day
);

CREATE INDEX IF NOT EXISTS idx_med_senior_date ON medication_adherence(senior_id, log_date);

-- ============================================
-- MATERIALIZED VIEWS (for dashboard performance)
-- ============================================

-- View 1: Latest Vitals for Each Senior (FAST dashboard query)
CREATE MATERIALIZED VIEW IF NOT EXISTS vw_latest_vitals_by_senior AS
SELECT DISTINCT ON (senior_id, vital_type)
    senior_id,
    vital_type,
    vital_value,
    unit,
    recorded_at
FROM senior_vitals
WHERE vital_type IN ('bp_systolic', 'bp_diastolic', 'heart_rate', 'weight', 'blood_sugar')
ORDER BY senior_id, vital_type, recorded_at DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_vitals ON vw_latest_vitals_by_senior(senior_id, vital_type);

-- View 2: 30-Day Cognitive Trend (for decline detection)
CREATE MATERIALIZED VIEW IF NOT EXISTS vw_cognitive_trend_30d AS
SELECT
    senior_id,
    DATE(assessment_date) as assessment_date,
    AVG(overall_score) as avg_score,
    COUNT(*) as assessment_count
FROM cognitive_assessments
WHERE assessment_date >= CURRENT_DATE - INTERVAL '30 days'
    AND overall_score IS NOT NULL
GROUP BY senior_id, DATE(assessment_date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_cognitive_trend ON vw_cognitive_trend_30d(senior_id, assessment_date DESC);

-- View 3: Weekly Medication Adherence Rate
CREATE MATERIALIZED VIEW IF NOT EXISTS vw_medication_adherence_weekly AS
SELECT
    senior_id,
    EXTRACT(YEAR FROM log_date)::INT as year,
    EXTRACT(WEEK FROM log_date)::INT as week_number,
    SUM(CASE WHEN medications_taken = true THEN 1 ELSE 0 END) as days_taken,
    COUNT(*) as total_days,
    ROUND(100.0 * SUM(CASE WHEN medications_taken = true THEN 1 ELSE 0 END) / COUNT(*), 1) as adherence_rate
FROM medication_adherence
GROUP BY senior_id, EXTRACT(YEAR FROM log_date), EXTRACT(WEEK FROM log_date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_med_adherence_weekly ON vw_medication_adherence_weekly(senior_id, year DESC, week_number DESC);

-- View 4: Active Health Alerts Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS vw_active_alerts_summary AS
SELECT
    senior_id,
    severity,
    alert_type,
    COUNT(*) as alert_count,
    MAX(alert_date) as latest_alert_date
FROM health_alerts
WHERE resolved = false
GROUP BY senior_id, severity, alert_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_active_alerts ON vw_active_alerts_summary(senior_id, severity, alert_type);

-- ============================================
-- HELPER VIEWS (Regular views, not materialized)
-- ============================================

-- Get latest value for each vital type per senior
CREATE OR REPLACE VIEW vw_senior_current_vitals AS
SELECT DISTINCT ON (senior_id, vital_type)
    senior_id,
    vital_type,
    vital_value,
    unit,
    recorded_at as last_recorded
FROM senior_vitals
ORDER BY senior_id, vital_type, recorded_at DESC;

-- Get 7-day summary for each senior
CREATE OR REPLACE VIEW vw_senior_7day_summary AS
SELECT
    cs.senior_id,
    COUNT(DISTINCT DATE(cs.call_date)) as calls_last_7_days,
    AVG(cs.overall_wellness) as avg_wellness,
    SUM(CASE WHEN cs.medication_adherence = true THEN 1 ELSE 0 END) as days_meds_taken,
    SUM(cs.red_flags_count) as total_red_flags,
    MAX(cs.call_date) as last_call_date
FROM call_summary cs
WHERE cs.call_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY cs.senior_id;

-- ============================================
-- REFRESH FUNCTIONS FOR MATERIALIZED VIEWS
-- ============================================

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_all_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_latest_vitals_by_senior;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_cognitive_trend_30d;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_medication_adherence_weekly;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_active_alerts_summary;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- USEFUL QUERIES FOR DASHBOARD
-- ============================================

/*
-- Query 1: Get current vital signs for a senior
SELECT * FROM vw_senior_current_vitals
WHERE senior_id = 'e6077e0e-334c-498d';

-- Query 2: Get cognitive decline trend
SELECT
    assessment_date,
    avg_score,
    LAG(avg_score, 1) OVER (ORDER BY assessment_date) as previous_score,
    avg_score - LAG(avg_score, 1) OVER (ORDER BY assessment_date) as score_change
FROM vw_cognitive_trend_30d
WHERE senior_id = 'e6077e0e-334c-498d'
ORDER BY assessment_date DESC;

-- Query 3: Get unresolved alerts
SELECT
    alert_type,
    severity,
    alert_count,
    latest_alert_date
FROM vw_active_alerts_summary
WHERE senior_id = 'e6077e0e-334c-498d'
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        ELSE 4
    END,
    latest_alert_date DESC;

-- Query 4: Get 7-day summary
SELECT * FROM vw_senior_7day_summary
WHERE senior_id = 'e6077e0e-334c-498d';

-- Query 5: Blood pressure trend (last 30 days)
SELECT
    DATE(recorded_at) as date,
    AVG(CASE WHEN vital_type = 'bp_systolic' THEN vital_value END) as systolic,
    AVG(CASE WHEN vital_type = 'bp_diastolic' THEN vital_value END) as diastolic
FROM senior_vitals
WHERE senior_id = 'e6077e0e-334c-498d'
    AND vital_type IN ('bp_systolic', 'bp_diastolic')
    AND recorded_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(recorded_at)
ORDER BY date DESC;

-- Query 6: Refresh materialized views (run periodically, e.g., hourly)
SELECT refresh_all_materialized_views();
*/
