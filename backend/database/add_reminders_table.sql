-- Add reminders table for upcoming appointments, events, tasks

CREATE TABLE IF NOT EXISTS senior_reminders (
    id BIGSERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    reminder_type VARCHAR(50) NOT NULL, -- 'appointment', 'medication_change', 'event', 'task', 'followup'
    title VARCHAR(200) NOT NULL,
    description TEXT,
    reminder_date DATE NOT NULL, -- When the event/appointment is
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed BOOLEAN DEFAULT false,
    completed_at TIMESTAMP,

    -- Categorization
    priority VARCHAR(20) DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
    category VARCHAR(50), -- 'doctor', 'family', 'social', 'health', 'personal'

    -- Who set the reminder
    created_by VARCHAR(100), -- 'agent', 'caregiver', 'family', 'self'

    -- For recurring reminders
    recurring BOOLEAN DEFAULT false,
    recurring_pattern VARCHAR(50) -- 'daily', 'weekly', 'monthly', null
);

CREATE INDEX IF NOT EXISTS idx_reminder_senior_date ON senior_reminders(senior_id, reminder_date);
CREATE INDEX IF NOT EXISTS idx_reminder_upcoming ON senior_reminders(senior_id, reminder_date, completed) WHERE completed = false;
CREATE INDEX IF NOT EXISTS idx_reminder_type ON senior_reminders(reminder_type, reminder_date);

-- View for upcoming reminders (next 7 days)
CREATE OR REPLACE VIEW vw_upcoming_reminders AS
SELECT
    senior_id,
    reminder_type,
    title,
    description,
    reminder_date,
    priority,
    category,
    (reminder_date - CURRENT_DATE) as days_until
FROM senior_reminders
WHERE completed = false
    AND reminder_date >= CURRENT_DATE
    AND reminder_date <= CURRENT_DATE + INTERVAL '7 days'
ORDER BY senior_id, reminder_date, priority DESC;

-- View for overdue reminders
CREATE OR REPLACE VIEW vw_overdue_reminders AS
SELECT
    senior_id,
    reminder_type,
    title,
    description,
    reminder_date,
    priority,
    (CURRENT_DATE - reminder_date) as days_overdue
FROM senior_reminders
WHERE completed = false
    AND reminder_date < CURRENT_DATE
ORDER BY senior_id, reminder_date;

COMMENT ON TABLE senior_reminders IS 'Stores reminders, appointments, and upcoming events for seniors';
COMMENT ON COLUMN senior_reminders.reminder_type IS 'Type: appointment, medication_change, event, task, followup';
COMMENT ON COLUMN senior_reminders.reminder_date IS 'Date of the event/appointment (not when to remind)';
