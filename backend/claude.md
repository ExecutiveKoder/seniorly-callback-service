## HIPAA Logging and PHI Redaction Policy

This repo must never emit Protected Health Information (PHI) to logs or console. Follow these rules for any future changes and contributions (including automated assistants):

### Do not log or print PHI
- Names, dates of birth, addresses, email addresses, phone numbers, contact IDs linked to a person
- Caller utterances, transcripts, AI responses containing user content
- Medical information: conditions, medications, vitals, assessments, reminders, summaries that include identifiable details

### Allowed logging patterns
- Structural/operational events without PHI: “WebSocket started”, “Call initiated”, “Call ended”, “Service initialized”
- Numerical metadata only: lengths, counts, durations, status codes, boolean flags
- IDs that are system-generated and not directly identifying on their own (OK to print the first 6–8 chars if needed)

### Preferred redaction techniques
- Replace sensitive values with fixed placeholders: "[suppressed]" or "(content suppressed)"
- For phone numbers: avoid printing; if unavoidable, mask to last 4 digits only
- For long texts (user/assistant messages): log only length, not content
- For objects/bodies from webhooks: do not log raw payloads

### Concrete examples
- Good: `logger.info("Initiating outbound call (destination and name suppressed)")`
- Good: `logger.info(f"Received response (length: {len(text)})")`
- Bad:  `logger.info(f"Caller said: {transcribed_text}")`
- Bad:  `print(f"Phone: {phone_number}")`

### Where this policy is enforced in code
- Twilio real-time service: `twilio_websocket_server.py` (no transcript/AI text logged)
- Kinesis processor: `kinesis_audio_processor.py` (no transcript/AI text logged)
- Webhooks: `webhook_server.py` (no raw bodies or greeting text logged)
- OpenAI client: `src/services/openai_service.py` (logs lengths only)
- Identity verification: `src/services/identity_verification_service.py` (names suppressed)
- Email: `src/services/email_service.py` (recipient and content suppressed)
- Config printout: `src/config.py` (phone masked)
- Local CLI: `src/main.py`, `run_app.sh`, `src/manage_profiles.py` (no names, DOBs, phones, user text printed)
- Telephony services: `src/services/twilio_service.py`, `src/services/aws_connect_service.py` (no names/phones logged)

### Additional guidance
- Do not add new logs that include PHI. If debugging requires content, write it to a developer-local buffer and never commit/ship it.
- Keep any PHI stored only in approved data stores (Cosmos, PostgreSQL) with access controls.
- Ensure transport encryption (TLS) and secret management (Key Vault) are in place.
- Prefer anonymized analytics; avoid exporting raw transcripts unless strictly required and properly access-controlled.

### Optional future enhancement
- Add a `MASK_PHI_LOGS=true` env flag to enforce redaction at runtime if needed. Current code already redacts by default.


