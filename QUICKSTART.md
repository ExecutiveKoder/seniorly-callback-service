# Quick Start Guide

## Get Running in 5 Minutes

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

**If pyaudio fails on macOS:**
```bash
brew install portaudio
pip install pyaudio
```

### 2. Run the Application

```bash
python src/main.py
```

### 3. Choose Testing Mode

**Option 2 - Text Mode (Recommended First)**
- Fastest way to test
- No microphone needed
- Type messages and see AI responses instantly

**Option 1 - Voice Mode**
- Full voice experience
- Requires working microphone and speakers
- Speak naturally and hear AI responses

### 4. Have a Conversation

The AI (named "Sarah") will:
- Greet you warmly
- Ask about your wellbeing
- Check on vitals and medications
- Listen to concerns
- Play subtle cognitive games
- Say goodbye

### Example Conversation (Text Mode)

```
🤖 Sarah: Hello! This is Sarah, your daily wellness companion. How are you doing today?

👤 You: I'm doing pretty well, thank you

🤖 Sarah: That's wonderful to hear! How did you sleep last night?

👤 You: I slept okay, about 6 hours

🤖 Sarah: Six hours is decent rest. Have you taken any measurements today,
like your blood pressure or heart rate?

👤 You: Yes, my blood pressure was 130 over 85

🤖 Sarah: Thank you for sharing that. How about your medications -
have you taken them today?

👤 You: goodbye

🤖 Sarah: Thank you for chatting with me today. Take care,
and I'll call you again tomorrow. Goodbye!
```

### 5. View Saved Conversations

```bash
python src/main.py
# Select option 3
# Enter the session ID shown at start of conversation
```

## What's Happening Behind the Scenes

1. **Your message** → Azure Speech (if voice mode) → Text
2. **GPT-5-CHAT** analyzes and generates empathetic response
3. **Response** → Azure Speech (if voice mode) → Voice
4. **Everything saved** to Cosmos DB for longitudinal analysis

## Next Steps

- Review `README.md` for full documentation
- Check `claude.md` for Azure infrastructure details
- Modify `src/senior_health_prompt.py` to customize AI behavior
- Test different voices by editing `.env` file

## Troubleshooting

**No microphone?**
- Use Option 2 (Text Mode)

**Azure connection errors?**
- Run Option 4 to test services
- Check `.env` file has all credentials

**Can't hear AI voice?**
- Check speaker volume
- Try Text Mode first to verify AI is working

## Ready for Phone Calls?

Once Azure approves your phone number:
1. Update `PHONE_NUMBER` in `.env`
2. Deploy to Azure Container Apps
3. Configure webhooks
4. Schedule automated daily calls

See `README.md` deployment section for details.
