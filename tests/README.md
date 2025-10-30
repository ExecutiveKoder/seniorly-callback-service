# Test Scripts

This directory contains test utilities for the Seniorly Voice Agent.

## Available Tests

### `test_voices.py`
**Purpose:** Test and compare different Azure Neural Voices

**Usage:**
```bash
python3 tests/test_voices.py
```

**Features:**
- Listen to 20+ Azure Neural Voices
- Test with sample senior care phrases
- Compare voice personalities and styles
- Update `.env` file with selected voice
- Test top 5 recommended voices for senior care

**Recommended Voices for Senior Care:**
1. Jenny - Warm and friendly
2. Aria - Professional yet warm
3. Sara - Gentle and caring
4. Michelle - Caring and warm
5. Guy - Calm and reassuring

### `test_twilio_call.py`
**Purpose:** Manual test script for making Twilio outbound calls

**Usage:**
```bash
python3 tests/test_twilio_call.py
```

**Note:** This script requires manual setup of ngrok and WebSocket server. For automated execution, use the main launcher script instead:
```bash
./run_app.sh
```

## Automated Testing

For production use, the `run_app.sh` script in the root directory automatically handles:
- Starting the WebSocket server
- Setting up ngrok tunnel
- Interactive call menu
- Automatic cleanup

Simply run:
```bash
./run_app.sh
```
