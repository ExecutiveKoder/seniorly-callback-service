-- Add comprehensive tracking tables for activity, falls, and chronic conditions

-- ============================================
-- ACTIVITY TRACKING TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS senior_activity (
    id BIGSERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    activity_date DATE NOT NULL,

    -- Physical activity metrics
    walked BOOLEAN DEFAULT false,
    walk_duration_minutes INT, -- How long they walked
    walk_distance VARCHAR(50), -- 'around block', '10 minutes', 'to mailbox'
    exercise_type VARCHAR(100), -- 'walking', 'stretching', 'yoga', 'swimming', 'gardening'
    exercise_duration_minutes INT,

    -- Daily activity level
    activity_level VARCHAR(20), -- 'sedentary', 'light', 'moderate', 'active'
    left_house BOOLEAN DEFAULT false,
    hours_out_of_bed INT, -- How many hours they were up and active

    -- Social activity
    social_interaction BOOLEAN DEFAULT false,
    social_type VARCHAR(100), -- 'phone call', 'visit', 'outing', 'video call'
    social_with VARCHAR(200), -- Who they interacted with

    -- Mobility
    mobility_aids_used VARCHAR(100), -- 'cane', 'walker', 'wheelchair', 'none'
    stairs_climbed BOOLEAN DEFAULT false,
    difficulty_moving BOOLEAN DEFAULT false,

    -- Notes
    notes TEXT,
    session_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(senior_id, activity_date)
);

CREATE INDEX IF NOT EXISTS idx_activity_senior_date ON senior_activity(senior_id, activity_date DESC);
CREATE INDEX IF NOT EXISTS idx_activity_level ON senior_activity(activity_level, activity_date);

-- ============================================
-- FALLS & INCIDENTS TRACKING TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS senior_falls (
    id BIGSERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    incident_date TIMESTAMP NOT NULL,

    -- Incident type
    incident_type VARCHAR(50) NOT NULL, -- 'fall', 'near_fall', 'loss_of_balance', 'dizzy_spell'

    -- Fall details
    location VARCHAR(100), -- 'bathroom', 'bedroom', 'kitchen', 'stairs', 'outside'
    activity_during VARCHAR(200), -- What they were doing when it happened
    injured BOOLEAN DEFAULT false,
    injury_type VARCHAR(200), -- 'bruise', 'cut', 'fracture', 'none'
    medical_attention BOOLEAN DEFAULT false,

    -- Contributing factors
    felt_dizzy BOOLEAN DEFAULT false,
    lost_balance BOOLEAN DEFAULT false,
    tripped BOOLEAN DEFAULT false,
    slipped BOOLEAN DEFAULT false,
    weakness BOOLEAN DEFAULT false,

    -- Circumstances
    time_of_day VARCHAR(20), -- 'morning', 'afternoon', 'evening', 'night'
    lighting VARCHAR(20), -- 'dark', 'dim', 'bright'
    rushed BOOLEAN DEFAULT false,

    -- Prevention/action taken
    reported_to_doctor BOOLEAN DEFAULT false,
    changes_made TEXT, -- What changes were made after incident

    -- Severity
    severity VARCHAR(20) DEFAULT 'minor', -- 'minor', 'moderate', 'severe', 'critical'

    notes TEXT,
    session_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_falls_senior_date ON senior_falls(senior_id, incident_date DESC);
CREATE INDEX IF NOT EXISTS idx_falls_type ON senior_falls(incident_type, incident_date);
CREATE INDEX IF NOT EXISTS idx_falls_severity ON senior_falls(severity, incident_date);

-- ============================================
-- CHRONIC CONDITIONS TRACKING TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS condition_tracking (
    id BIGSERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    tracking_date DATE NOT NULL,
    condition_name VARCHAR(100) NOT NULL, -- 'diabetes', 'hypertension', 'arthritis', 'copd', etc.

    -- Status
    status VARCHAR(20) DEFAULT 'stable', -- 'improving', 'stable', 'worsening', 'flare-up'

    -- Symptoms today
    symptoms_present BOOLEAN DEFAULT false,
    symptom_severity INT, -- 1-10 scale
    symptom_description TEXT,

    -- Management
    following_treatment BOOLEAN DEFAULT true,
    medication_adherence BOOLEAN DEFAULT true,
    lifestyle_adherence BOOLEAN DEFAULT true, -- Diet, exercise, etc.

    -- Impact
    impact_on_daily_life INT, -- 1-10 scale (1=no impact, 10=severe impact)
    limited_activities BOOLEAN DEFAULT false,
    activities_limited TEXT, -- What activities they couldn't do

    -- Recent changes
    new_symptoms BOOLEAN DEFAULT false,
    symptoms_changed TEXT,
    medication_changed BOOLEAN DEFAULT false,

    -- Doctor interaction
    doctor_visit_upcoming BOOLEAN DEFAULT false,
    doctor_visit_date DATE,
    concerns_for_doctor TEXT,

    notes TEXT,
    session_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(senior_id, tracking_date, condition_name)
);

CREATE INDEX IF NOT EXISTS idx_condition_senior_date ON condition_tracking(senior_id, tracking_date DESC);
CREATE INDEX IF NOT EXISTS idx_condition_name ON condition_tracking(condition_name, tracking_date);
CREATE INDEX IF NOT EXISTS idx_condition_status ON condition_tracking(status, tracking_date);

-- ============================================
-- VIEWS FOR TRENDING & ANALYSIS
-- ============================================

-- Activity trend (last 30 days)
CREATE OR REPLACE VIEW vw_activity_trend_30d AS
SELECT
    senior_id,
    DATE_TRUNC('week', activity_date) as week_start,
    COUNT(*) as days_active,
    SUM(CASE WHEN walked THEN 1 ELSE 0 END) as days_walked,
    AVG(walk_duration_minutes) as avg_walk_minutes,
    SUM(CASE WHEN left_house THEN 1 ELSE 0 END) as days_left_house,
    SUM(CASE WHEN social_interaction THEN 1 ELSE 0 END) as days_social,
    AVG(hours_out_of_bed) as avg_hours_active
FROM senior_activity
WHERE activity_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY senior_id, DATE_TRUNC('week', activity_date)
ORDER BY senior_id, week_start DESC;

-- Falls risk assessment (last 90 days)
CREATE OR REPLACE VIEW vw_falls_risk_90d AS
SELECT
    senior_id,
    COUNT(*) as fall_count,
    SUM(CASE WHEN incident_type = 'fall' THEN 1 ELSE 0 END) as actual_falls,
    SUM(CASE WHEN incident_type = 'near_fall' THEN 1 ELSE 0 END) as near_falls,
    SUM(CASE WHEN injured THEN 1 ELSE 0 END) as falls_with_injury,
    MAX(incident_date) as last_fall_date,
    (CURRENT_DATE - MAX(incident_date)::DATE) as days_since_last_fall,
    -- Risk calculation
    CASE
        WHEN COUNT(*) >= 3 THEN 'high'
        WHEN COUNT(*) >= 1 THEN 'moderate'
        ELSE 'low'
    END as risk_level
FROM senior_falls
WHERE incident_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY senior_id;

-- Chronic condition status
CREATE OR REPLACE VIEW vw_condition_current_status AS
SELECT DISTINCT ON (senior_id, condition_name)
    senior_id,
    condition_name,
    status,
    symptom_severity,
    impact_on_daily_life,
    tracking_date,
    following_treatment,
    new_symptoms
FROM condition_tracking
ORDER BY senior_id, condition_name, tracking_date DESC;

-- Condition deterioration alerts (status worsening)
CREATE OR REPLACE VIEW vw_condition_alerts AS
WITH latest_status AS (
    SELECT DISTINCT ON (senior_id, condition_name)
        senior_id,
        condition_name,
        status,
        tracking_date,
        impact_on_daily_life
    FROM condition_tracking
    ORDER BY senior_id, condition_name, tracking_date DESC
)
SELECT
    senior_id,
    condition_name,
    status,
    tracking_date,
    impact_on_daily_life
FROM latest_status
WHERE status IN ('worsening', 'flare-up')
    OR impact_on_daily_life >= 7
    OR tracking_date >= CURRENT_DATE - INTERVAL '7 days';

COMMENT ON TABLE senior_activity IS 'Daily activity tracking - walking, exercise, social interaction, mobility';
COMMENT ON TABLE senior_falls IS 'Fall incidents and near-falls with detailed circumstances';
COMMENT ON TABLE condition_tracking IS 'Daily tracking of chronic conditions and symptom management';
