-- ============================================
-- SENIOR HEALTH ANALYTICS DATABASE SCHEMA
-- Azure SQL Database
-- ============================================

-- Table 1: Senior Vitals (flexible, handles sparse data)
CREATE TABLE senior_vitals (
    id BIGINT PRIMARY KEY IDENTITY(1,1),
    senior_id VARCHAR(50) NOT NULL,
    recorded_at DATETIME2 NOT NULL,
    vital_type VARCHAR(50) NOT NULL,
    -- Examples: 'bp_systolic', 'bp_diastolic', 'heart_rate', 'weight',
    --           'blood_sugar', 'sleep_hours', 'pain_level', 'temperature'
    vital_value DECIMAL(10,2) NOT NULL,
    unit VARCHAR(20) NOT NULL, -- 'mmHg', 'bpm', 'lbs', 'hours', 'scale', 'mg/dL'
    source VARCHAR(50) DEFAULT 'call', -- 'call', 'device', 'manual', 'self_reported'
    session_id VARCHAR(50), -- Link back to conversation session
    created_at DATETIME2 DEFAULT GETDATE(),
    INDEX idx_senior_date (senior_id, recorded_at),
    INDEX idx_vital_type (vital_type, recorded_at),
    INDEX idx_session (session_id)
);

-- Table 2: Cognitive Assessments (daily cognitive health scores)
CREATE TABLE cognitive_assessments (
    id BIGINT PRIMARY KEY IDENTITY(1,1),
    senior_id VARCHAR(50) NOT NULL,
    assessment_date DATETIME2 NOT NULL,

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
    created_at DATETIME2 DEFAULT GETDATE(),

    INDEX idx_senior_date (senior_id, assessment_date),
    INDEX idx_overall_score (overall_score, assessment_date)
);

-- Table 3: Call Summary (daily call overview)
CREATE TABLE call_summary (
    id BIGINT PRIMARY KEY IDENTITY(1,1),
    senior_id VARCHAR(50) NOT NULL,
    call_date DATETIME2 NOT NULL,
    session_id VARCHAR(50) NOT NULL,

    -- Call details
    call_duration INT, -- seconds
    call_completed BIT NOT NULL DEFAULT 1,
    call_answered BIT NOT NULL DEFAULT 1,

    -- Wellness scores (1-10 scale)
    overall_wellness INT, -- Nullable if not assessed
    physical_health INT,
    mental_health INT,
    social_engagement INT,

    -- Specific checks
    medication_adherence BIT, -- NULL if not asked/answered
    medication_missed_count INT DEFAULT 0,

    -- Sentiment analysis
    mood_sentiment DECIMAL(5,2), -- -1 (very negative) to 1 (very positive)
    engagement_level INT, -- 0-10 scale

    -- Alerts and concerns
    red_flags_count INT DEFAULT 0,
    red_flags NVARCHAR(MAX), -- JSON array of alert types

    -- AI-generated summary
    summary_text TEXT,

    created_at DATETIME2 DEFAULT GETDATE(),

    INDEX idx_senior_date (senior_id, call_date),
    INDEX idx_session (session_id),
    INDEX idx_red_flags (red_flags_count, call_date)
);

-- Table 4: Health Alerts (track concerning patterns)
CREATE TABLE health_alerts (
    id BIGINT PRIMARY KEY IDENTITY(1,1),
    senior_id VARCHAR(50) NOT NULL,
    alert_date DATETIME2 NOT NULL,
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
    resolved BIT DEFAULT 0,
    resolved_at DATETIME2,
    resolved_by VARCHAR(100), -- caregiver name or system
    resolution_notes TEXT,

    created_at DATETIME2 DEFAULT GETDATE(),

    INDEX idx_senior_date (senior_id, alert_date),
    INDEX idx_severity (severity, alert_date),
    INDEX idx_unresolved (resolved, alert_date)
);

-- Table 5: Medication Adherence Log
CREATE TABLE medication_adherence (
    id BIGINT PRIMARY KEY IDENTITY(1,1),
    senior_id VARCHAR(50) NOT NULL,
    log_date DATE NOT NULL,

    medications_taken BIT, -- Overall adherence
    medications_missed_count INT DEFAULT 0,
    specific_medications TEXT, -- JSON array of medications discussed

    side_effects_reported BIT DEFAULT 0,
    side_effects_description TEXT,

    session_id VARCHAR(50),
    created_at DATETIME2 DEFAULT GETDATE(),

    INDEX idx_senior_date (senior_id, log_date),
    UNIQUE (senior_id, log_date) -- One record per senior per day
);

-- ============================================
-- MATERIALIZED VIEWS (Indexed Views in SQL Server)
-- ============================================

-- View 1: Latest Vitals for Each Senior (FAST dashboard query)
GO
CREATE VIEW vw_latest_vitals_by_senior
WITH SCHEMABINDING
AS
SELECT
    senior_id,
    vital_type,
    vital_value,
    unit,
    recorded_at,
    COUNT_BIG(*) AS row_count
FROM dbo.senior_vitals
WHERE vital_type IN ('bp_systolic', 'bp_diastolic', 'heart_rate', 'weight', 'blood_sugar')
GROUP BY senior_id, vital_type, vital_value, unit, recorded_at;
GO

-- Create clustered index to materialize the view
CREATE UNIQUE CLUSTERED INDEX idx_latest_vitals
ON vw_latest_vitals_by_senior(senior_id, vital_type, recorded_at DESC);
GO

-- View 2: 30-Day Cognitive Trend (for decline detection)
GO
CREATE VIEW vw_cognitive_trend_30d
WITH SCHEMABINDING
AS
SELECT
    senior_id,
    CAST(assessment_date AS DATE) as assessment_date,
    AVG(CAST(overall_score AS FLOAT)) as avg_score,
    COUNT_BIG(*) as assessment_count
FROM dbo.cognitive_assessments
WHERE assessment_date >= DATEADD(day, -30, CAST(GETDATE() AS DATE))
    AND overall_score IS NOT NULL
GROUP BY senior_id, CAST(assessment_date AS DATE);
GO

CREATE UNIQUE CLUSTERED INDEX idx_cognitive_trend
ON vw_cognitive_trend_30d(senior_id, assessment_date DESC);
GO

-- View 3: Weekly Medication Adherence Rate
GO
CREATE VIEW vw_medication_adherence_weekly
WITH SCHEMABINDING
AS
SELECT
    senior_id,
    DATEPART(year, log_date) as year,
    DATEPART(week, log_date) as week_number,
    SUM(CASE WHEN medications_taken = 1 THEN 1 ELSE 0 END) as days_taken,
    COUNT_BIG(*) as total_days,
    CAST(ROUND(100.0 * SUM(CASE WHEN medications_taken = 1 THEN 1 ELSE 0 END) / COUNT_BIG(*), 1) AS DECIMAL(5,2)) as adherence_rate
FROM dbo.medication_adherence
GROUP BY senior_id, DATEPART(year, log_date), DATEPART(week, log_date);
GO

CREATE UNIQUE CLUSTERED INDEX idx_med_adherence_weekly
ON vw_medication_adherence_weekly(senior_id, year DESC, week_number DESC);
GO

-- View 4: Active Health Alerts Summary
GO
CREATE VIEW vw_active_alerts_summary
WITH SCHEMABINDING
AS
SELECT
    senior_id,
    severity,
    alert_type,
    COUNT_BIG(*) as alert_count,
    MAX(alert_date) as latest_alert_date
FROM dbo.health_alerts
WHERE resolved = 0
GROUP BY senior_id, severity, alert_type;
GO

CREATE UNIQUE CLUSTERED INDEX idx_active_alerts
ON vw_active_alerts_summary(senior_id, severity, alert_type);
GO

-- ============================================
-- HELPER VIEWS (Regular views, not materialized)
-- ============================================

-- Get latest value for each vital type per senior
GO
CREATE VIEW vw_senior_current_vitals AS
WITH RankedVitals AS (
    SELECT
        senior_id,
        vital_type,
        vital_value,
        unit,
        recorded_at,
        ROW_NUMBER() OVER (PARTITION BY senior_id, vital_type ORDER BY recorded_at DESC) as rn
    FROM senior_vitals
)
SELECT
    senior_id,
    vital_type,
    vital_value,
    unit,
    recorded_at as last_recorded
FROM RankedVitals
WHERE rn = 1;
GO

-- Get 7-day summary for each senior
GO
CREATE VIEW vw_senior_7day_summary AS
SELECT
    cs.senior_id,
    COUNT(DISTINCT cs.call_date) as calls_last_7_days,
    AVG(cs.overall_wellness) as avg_wellness,
    SUM(CASE WHEN cs.medication_adherence = 1 THEN 1 ELSE 0 END) as days_meds_taken,
    SUM(cs.red_flags_count) as total_red_flags,
    MAX(cs.call_date) as last_call_date
FROM call_summary cs
WHERE cs.call_date >= DATEADD(day, -7, CAST(GETDATE() AS DATE))
GROUP BY cs.senior_id;
GO

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
    CAST(recorded_at AS DATE) as date,
    AVG(CASE WHEN vital_type = 'bp_systolic' THEN vital_value END) as systolic,
    AVG(CASE WHEN vital_type = 'bp_diastolic' THEN vital_value END) as diastolic
FROM senior_vitals
WHERE senior_id = 'e6077e0e-334c-498d'
    AND vital_type IN ('bp_systolic', 'bp_diastolic')
    AND recorded_at >= DATEADD(day, -30, GETDATE())
GROUP BY CAST(recorded_at AS DATE)
ORDER BY date DESC;
*/
