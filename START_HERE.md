# 🚀 START HERE - Quick Commands

## ✅ Everything is Installed and Ready!

### Run the Senior Profile Manager
```bash
./run_profiles.sh
```

**What it does:**
- Add new seniors (name, phone, medical info)
- View senior profiles
- List all seniors
- Search by phone number
- Update profiles
- View call history

---

### Run the Voice Agent Application
```bash
./run_app.sh
```

**Menu Options:**
1. **Voice Mode** - Talk using microphone (NOW AVAILABLE!)
2. **Text Mode** - Type messages (faster for testing)
3. **View Conversation History** - See past conversations
4. **Test Services** - Check Azure connections
5. **Exit**

---

## 📝 Quick Testing Workflow

### 1. Add a Test Senior
```bash
./run_profiles.sh
# Select: 1 (Add New Senior)
# Enter: John Doe, +1-555-123-4567, etc.
```

### 2. Test Text Conversation
```bash
./run_app.sh
# Select: 2 (Text Mode)
# Type: Hello
# AI will respond
# Type: goodbye (to end)
```

### 3. Test Voice Conversation
```bash
./run_app.sh
# Select: 1 (Voice Mode)
# Speak into microphone
# AI responds through speakers
```

### 4. Test Safety Features
In text mode, try:
- "I'm having chest pain" → EMERGENCY alert
- "My caregiver hit me" → URGENT abuse alert
- "What about politics?" → Redirects to health topic

---

## 🔧 Manual Activation (if scripts don't work)

```bash
source venv/bin/activate
python src/manage_profiles.py    # Profile manager
python src/main.py                # Voice agent
```

---

## 📚 Documentation

- **QUICKSTART.md** - 5-minute setup guide
- **README.md** - Complete technical docs
- **SAFETY.md** - Safety guardrails & protocols
- **SUMMARY.md** - Full project overview

---

## 🆘 Troubleshooting

**Microphone not working?**
- Check System Settings → Privacy & Security → Microphone
- Grant permission to Terminal

**Module not found errors?**
- Make sure you activated: `source venv/bin/activate`

**Azure connection issues?**
- Run: `./run_app.sh` → Select 4 (Test Services)

---

## 🎯 What to Test

### Safety Monitoring (Text Mode)
Try these phrases:
- "I want to end my life"
- "I haven't eaten in days"
- "Someone is stealing my money"
- "Should I invest in crypto?"

Watch the safety alerts trigger!

### Conversation Flow
The AI should:
- Greet warmly
- Ask about sleep
- Check vitals
- Ask about medications
- Listen to concerns
- Play cognitive games naturally
- Say goodbye warmly

### Topic Control
Try off-topic:
- "Tell me about the news"
- "Can you fix my computer?"
- "What stocks should I buy?"

AI should redirect back to health!

---

## 💡 Next Steps

1. ✅ Test profile management
2. ✅ Test text conversations
3. ✅ Test voice conversations
4. ✅ Review safety alerts
5. ⏳ Wait for phone number
6. 🚀 Deploy to production

---

## 🎉 You're Ready!

All systems operational. All safety guardrails active. Database containers created.

**Start testing now:**
```bash
./run_profiles.sh
```

or

```bash
./run_app.sh
```

**Questions?** Check the documentation files or run test services option.
