# Safety & Protection Framework

## Overview

This Senior Health Monitoring AI has **comprehensive safety guardrails** to protect vulnerable seniors from harm, abuse, and inappropriate content. Safety is the #1 priority.

---

## 🛡️ Multi-Layer Safety Architecture

### Layer 1: AI System Prompt Guardrails
**Location:** `src/senior_health_prompt.py`

Built directly into GPT-5-CHAT's instructions with 10 critical safety categories:

1. **Never Give Medical Advice**
   - No medication recommendations
   - No diagnoses or treatment suggestions
   - Always defers to healthcare providers

2. **Never Suggest Harmful Actions**
   - No self-harm suggestions
   - No harm to others
   - No isolation or withdrawal from care

3. **No Financial Advice or Transactions**
   - No investment or money advice
   - No purchases or donations
   - Warns about potential scams

4. **Protection from Emotional Manipulation**
   - No guilt, fear, or pressure tactics
   - Never asks to keep secrets
   - Never suggests they're a burden

5. **Abuse & Neglect Recognition**
   - Detects physical abuse indicators
   - Detects emotional abuse patterns
   - Detects financial exploitation
   - Detects neglect situations

6. **Emergency Response Protocols**
   - Medical emergencies → Call 911
   - Suicide risk → 988 Crisis Lifeline
   - Active threats → Immediate escalation

7. **Autonomy & Dignity Respect**
   - Treats seniors as capable adults
   - Never condescending
   - Respects choices and boundaries

8. **Privacy Protection**
   - No sharing unauthorized information
   - Never asks for passwords/PINs
   - Confidential conversations

9. **Mental Health Protection**
   - Takes depression seriously
   - Provides crisis resources
   - Never dismisses suicidal thoughts

10. **Medication Safety**
    - Never adjusts prescribed medications
    - Tracks adherence only
    - Reports side effects to provider

### Layer 2: Real-Time Safety Monitoring
**Location:** `src/services/safety_service.py`

Automated pattern detection system that analyzes every message for:

**Emergency Medical Situations:**
- Chest pain, heart attack symptoms
- Difficulty breathing
- Stroke symptoms (FAST protocol)
- Severe bleeding or injury
- Fall unable to get up
- Loss of consciousness

**Suicide & Self-Harm:**
- Suicidal ideation
- Self-harm plans or actions
- Hopelessness expressions
- Goodbye messages

**Physical Abuse:**
- Reports of hitting, beating, pushing
- Bruises or injuries
- Fear of caregiver
- Restrained or locked up

**Emotional Abuse:**
- Yelling, screaming, name-calling
- Threats and intimidation
- Humiliation or degradation
- Isolation from others

**Financial Exploitation:**
- Money being taken
- Forced signatures
- Unauthorized transactions
- Account draining

**Neglect:**
- No food or water
- Missing medications
- Unsanitary conditions
- Left alone for extended periods

**Medication Issues:**
- Overdose or wrong dosage
- Running out of medications
- Adverse reactions
- Mixing dangerous combinations

### Layer 3: Topic Boundaries
**Location:** `src/senior_health_prompt.py` (Stay on Topic section)

AI is instructed to politely redirect off-topic conversations:

**Allowed Topics:**
- Health and wellness
- Sleep and rest
- Vitals and symptoms
- Medications
- Daily activities
- Cognitive games
- Social connections
- Mood and feelings

**Blocked Topics (with gentle redirection):**
- Politics and religion
- Financial advice
- Legal advice
- Technology troubleshooting
- Detailed medical treatment plans
- Celebrity gossip and news
- Shopping recommendations
- Task requests (making calls, placing orders)

---

## 🚨 Alert Levels

### NONE
No safety concerns detected. Normal conversation.

### INFO
Informational note logged but no action required.

### WARNING
Potential concern that should be reviewed.
- Example: Medication confusion
- Action: Monitor in next call

### URGENT
Serious concern requiring follow-up within 24 hours.
- Examples: Abuse indicators, neglect, financial exploitation
- Action: Contact Adult Protective Services

### EMERGENCY
Life-threatening situation requiring immediate action.
- Examples: Medical emergency, suicide risk, active abuse
- Action: Call 911, 988 Crisis Lifeline, or appropriate emergency service

---

## 📊 Safety Monitoring in Action

### During Conversations

Every message is automatically analyzed:

```python
# Automatic safety check on every message
safety_analysis = safety_monitor.analyze_message(content, role)

# If alert detected:
if safety_analysis["alert_level"] != AlertLevel.NONE:
    # Log warning
    # Display alert to operator
    # Save to database with metadata
    # Provide crisis resources if emergency
```

### Alert Output Example

```
⚠️ SAFETY ALERT: URGENT
Categories: abuse_physical, abuse_emotional
Recommended Action: ABUSE ALERT - Contact Adult Protective Services
Matched 2 concerning pattern(s)
```

### Emergency Output Example

```
============================================================
🚨 EMERGENCY DETECTED - IMMEDIATE ACTION REQUIRED
============================================================
Recommended Action: CALL 911 IMMEDIATELY - Medical emergency detected

Crisis Resources:
  - suicide_crisis: 988 Suicide & Crisis Lifeline (call or text 988)
  - elder_abuse: National Elder Abuse Hotline: 1-800-677-1116
  - emergency: 911 for immediate life-threatening emergencies
  - domestic_violence: National Domestic Violence Hotline: 1-800-799-7233
  - poison_control: Poison Control: 1-800-222-1222
  - medicare: Medicare Fraud Hotline: 1-800-633-4227
============================================================
```

---

## 🔍 What Gets Monitored

### User Messages (Senior's Words)
- Emergency keywords
- Abuse indicators
- Suicide/self-harm expressions
- Neglect reports
- Medication problems

### AI Responses (System Output)
- Harmful advice detection
- Medical advice (blocked)
- Financial advice (blocked)
- Secret-keeping requests (blocked)
- Invalidating language (blocked)

### Conversation Patterns
- Repetition or confusion (cognitive)
- Mood changes over time
- Medication non-adherence
- Social isolation indicators
- Pain escalation

---

## 📝 Data Storage & Privacy

### What Gets Saved

**Cosmos DB (Permanent Storage):**
- Full conversation transcript
- Safety analysis metadata
- Alert levels and categories
- Timestamps
- Session information

**Redis Cache (Temporary):**
- Active session state
- Recent conversation context
- TTL: 1 hour (auto-deleted)

### Data Security

✅ **Encrypted at rest** (Azure encryption)
✅ **Encrypted in transit** (TLS 1.2+)
✅ **Access controlled** (Azure RBAC)
✅ **Audit logged** (Azure Monitor)
✅ **HIPAA considerations documented**

⚠️ **For Production:**
- Obtain Business Associate Agreement (BAA) from Microsoft
- Enable Advanced Threat Protection
- Implement data retention policies
- Add PHI-specific encryption
- Complete security assessment

---

## 🚦 Response Protocols

### When Safety Alert Triggers

1. **Log Alert**
   - Written to application logs
   - Severity level recorded
   - Timestamp captured

2. **Display to Operator**
   - Visual alert in terminal
   - Alert level and category
   - Recommended action

3. **Save to Database**
   - Full analysis in metadata
   - Searchable by alert type
   - Longitudinal tracking

4. **Provide Resources**
   - Crisis hotlines
   - Emergency contacts
   - Next steps guidance

5. **Continue Conversation**
   - AI maintains empathy
   - Stays engaged with senior
   - Does not alarm them
   - Follows safety protocols in responses

### Escalation Paths

**EMERGENCY → Immediate**
- Display crisis resources
- Log critical alert
- (Future) Auto-notify emergency contact
- (Future) Trigger emergency services

**URGENT → Within 24 hours**
- Flag for case manager review
- Log detailed incident
- (Future) Notify family/caregiver
- (Future) Schedule follow-up call

**WARNING → Next scheduled call**
- Note in senior's profile
- Monitor in next conversation
- Track pattern over time

---

## 🎯 Testing Safety Features

### Test Emergency Detection

```bash
python src/main.py
# Choose Option 2 (Text Mode)

# Try these test phrases:
"I'm having chest pain"
"I want to end my life"
"My caregiver hit me yesterday"
"I haven't eaten in two days"
```

**Expected:** Safety alerts should trigger immediately with appropriate resources.

### Test Topic Redirection

```bash
# Try these off-topic phrases:
"What do you think about the election?"
"Should I invest in bitcoin?"
"Can you call my doctor for me?"
```

**Expected:** AI should politely redirect back to health topics.

### Test Harmful Advice Blocking

The AI should **NEVER** say:
- "You should stop taking your medication"
- "Try this herbal remedy instead"
- "Don't bother your doctor about that"
- "You're overreacting"
- "Keep this between us"

**Expected:** Safety monitor should catch and flag any such responses.

---

## 📚 Crisis Resources (Always Available)

### Emergency Services
- **911** - Life-threatening medical emergencies
- **988** - Suicide & Crisis Lifeline (call or text)

### Abuse & Neglect
- **1-800-677-1116** - National Elder Abuse Hotline
- **1-800-799-7233** - National Domestic Violence Hotline
- **Adult Protective Services** - Local (varies by state)

### Health
- **1-800-222-1222** - Poison Control
- **1-800-633-4227** - Medicare Fraud Hotline

### Provider Contact
- Senior's primary care physician
- Pharmacy
- Home health agency
- Care coordinator

---

## 🔧 Customizing Safety Rules

### Add New Keywords

Edit `src/services/safety_service.py`:

```python
# Add to existing patterns
self.emergency_medical_patterns.append(
    r"\bnew emergency keyword\b"
)
```

### Adjust Alert Levels

Modify severity in `safety_service.py`:

```python
if pattern.search(message):
    result["alert_level"] = AlertLevel.EMERGENCY.value  # Change as needed
```

### Modify AI Instructions

Edit `src/senior_health_prompt.py`:

```python
SENIOR_HEALTH_SYSTEM_PROMPT = """
[Add additional safety rules here]
"""
```

---

## ⚖️ Legal & Compliance

### Mandatory Reporting

**Many states require reporting of elder abuse.** Consult with legal counsel to ensure compliance with:
- State mandatory reporting laws
- HIPAA requirements
- Adult Protective Services protocols
- Duty to warn obligations

### Documentation

All safety alerts are automatically documented with:
- Exact timestamp
- Full conversation context
- Alert category and severity
- Recommended actions
- Stored in Cosmos DB for audit trail

### Liability Protection

This system provides:
✅ Consistent safety monitoring
✅ Documented decision-making
✅ Clear escalation protocols
✅ Crisis resource provision
✅ Audit trail maintenance

⚠️ **Consult legal and compliance professionals before production use.**

---

## 🎓 Training for Care Teams

### What Care Teams Should Know

1. **AI Limitations**
   - This is a monitoring tool, not a replacement for human care
   - AI can miss nuanced situations
   - Always review flagged alerts

2. **Alert Response**
   - EMERGENCY alerts require immediate action
   - URGENT alerts require same-day review
   - WARNING alerts tracked over time

3. **False Positives**
   - Keyword detection may trigger unnecessarily
   - Review context before escalating
   - Senior may use concerning words casually

4. **Privacy**
   - Explain to seniors that calls are monitored for safety
   - Get consent for recording/storage
   - Respect senior autonomy

---

## 📊 Safety Metrics to Track

### Key Performance Indicators

- **Alert Rate:** % of calls with safety alerts
- **Response Time:** Time from alert to action
- **False Positive Rate:** Alerts that didn't require action
- **Emergency Detection:** True emergencies caught
- **Abuse Reports:** Cases referred to APS
- **Resource Utilization:** Crisis hotline referrals

### Monthly Review

Analyze:
- Most common alert types
- Seniors with repeat alerts
- AI response effectiveness
- System improvements needed

---

## 🔐 Security Considerations

### Prevent Misuse

✅ Access control on dashboards
✅ Audit logs for all data access
✅ No PHI in logs or error messages
✅ Secure API endpoints
✅ Rate limiting on calls
✅ Authentication required

### Data Breach Response

1. Immediately revoke access
2. Notify affected individuals
3. Report per HIPAA rules (if applicable)
4. Document incident
5. Remediate vulnerability
6. Review and improve security

---

## 🚀 Future Safety Enhancements

### Planned Features

- [ ] Real-time alert dashboard for care teams
- [ ] Automatic emergency contact notification
- [ ] Integration with EHR systems for medical history context
- [ ] Advanced NLP for sentiment analysis
- [ ] Voice stress analysis (if available from Azure Speech)
- [ ] Cognitive decline scoring algorithms
- [ ] Family portal for safety alert review
- [ ] Integration with Adult Protective Services systems
- [ ] Compliance reporting automation

---

## ✅ Safety Checklist for Production

Before deploying to production with real seniors:

- [ ] Legal review of safety protocols
- [ ] HIPAA compliance assessment
- [ ] Obtain Business Associate Agreement (BAA)
- [ ] Test all safety scenarios
- [ ] Train care team on alert response
- [ ] Set up 24/7 alert monitoring
- [ ] Establish emergency escalation process
- [ ] Create incident response plan
- [ ] Document all safety procedures
- [ ] Get liability insurance
- [ ] Obtain senior/family consent
- [ ] Configure secure access controls
- [ ] Enable audit logging
- [ ] Schedule regular safety audits

---

**Remember: Safety is not optional. Every conversation is monitored. Every alert is logged. When in doubt, escalate.**
