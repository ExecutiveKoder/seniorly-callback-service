# Advanced Noise Filtering for Voice Agent

## Problem
The voice agent was too sensitive to background noise, responding to:
- TV or radio in the background
- Distant conversations
- Brief sounds or clicks
- Any audio that wasn't the person speaking directly into the phone

## Solution: Multi-Layer Voice Activity Detection (VAD)

We implemented a 4-layer filtering system plus sustained speech detection to ensure only close-proximity human speech triggers responses.

### Layer 1: Volume Threshold (RMS Energy)
**What it does:** Measures the loudness of audio
**Threshold:** 0.05 (increased from 0.02)
**Purpose:** Requires louder audio = person must be closer to microphone

```python
rms = sqrt(mean(audio^2))
if rms < 0.05: reject
```

### Layer 2: Zero-Crossing Rate (ZCR)
**What it does:** Counts how often the audio signal crosses zero
**Expected range:** 0.003 - 0.04
**Purpose:** Human speech has moderate ZCR; TV/music has higher ZCR; constant noise has very low ZCR

```python
zcr = zero_crossings / audio_length
if zcr < 0.003 or zcr > 0.04: reject
```

### Layer 3: Dynamic Range
**What it does:** Measures the ratio between peak volume and average volume
**Expected range:** > 2.0
**Purpose:** Speech has clear peaks and valleys; background noise is more uniform

```python
dynamic_range = peak_amplitude / rms
if dynamic_range < 2.0: reject
```

### Layer 4: Spectral Centroid
**What it does:** Measures the frequency content of audio
**Expected range:** 200-3800 Hz
**Purpose:** Human speech is mostly 300-3400 Hz; background noise often has different frequency profiles

```python
spectral_centroid = sum(frequencies * magnitudes) / sum(magnitudes)
if centroid < 200 Hz or centroid > 3800 Hz: reject
```

### Layer 5: Sustained Speech Detection
**What it does:** Requires multiple consecutive chunks of valid speech
**Requirement:** 2 consecutive chunks (~4 seconds total)
**Purpose:** Prevents brief background noises from triggering responses

```python
if speech_counter < 2:
    continue accumulating
else:
    process speech
```

## How It Works

```
Incoming Audio (every 2 seconds)
    ↓
Layer 1: Volume Check
    ↓ (pass)
Layer 2: Speech Pattern Check (ZCR)
    ↓ (pass)
Layer 3: Dynamic Range Check
    ↓ (pass)
Layer 4: Frequency Check (Spectral Centroid)
    ↓ (pass)
Layer 5: Sustained Speech Check
    ↓ (2+ chunks)
✅ Process with Azure Speech STT
```

## Logging Output Examples

### Background Noise (Rejected)
```
❌ Audio too quiet (RMS: 0.023 < 0.05)
🔇 Background noise detected, ignoring
```

### TV Noise (Rejected)
```
✅ Volume OK (RMS: 0.06)
❌ Unusual speech pattern (ZCR: 0.052, expected 0.003-0.04)
🔇 Background noise detected, ignoring
```

### Valid Speech (Accepted)
```
✅ Valid speech detected (RMS: 0.08, ZCR: 0.012, Dynamic: 3.2)
🎤 Speech detected (1/2 chunks), continuing...
✅ Valid speech detected (RMS: 0.09, ZCR: 0.015, Dynamic: 3.5)
🎤 Speech detected (2/2 chunks), continuing...
✅ Sustained speech confirmed, processing...
```

## Adjusting Sensitivity

If the system is **too strict** (missing valid speech):

```python
# Option 1: Lower volume threshold
has_significant_audio(pcm_data, threshold=0.03)  # Default: 0.05

# Option 2: Reduce sustained speech requirement
SPEECH_CHUNKS_REQUIRED = 1  # Default: 2

# Option 3: Widen ZCR range
if zcr < 0.002 or zcr > 0.05: reject  # Default: 0.003-0.04
```

If the system is **too lenient** (still catching background noise):

```python
# Option 1: Increase volume threshold
has_significant_audio(pcm_data, threshold=0.08)  # Default: 0.05

# Option 2: Increase sustained speech requirement
SPEECH_CHUNKS_REQUIRED = 3  # Default: 2

# Option 3: Increase dynamic range requirement
if dynamic_range < 2.5: reject  # Default: 2.0
```

## Technical Details

### Audio Format
- **Sample rate:** 8 kHz (Twilio standard)
- **Encoding:** mulaw → 16-bit PCM
- **Chunk size:** 16,000 bytes (2 seconds of audio)
- **Processing:** Real-time, every 2 seconds

### Performance Impact
- **Latency added:** ~10-20ms per check (negligible)
- **CPU usage:** Minimal (simple math operations)
- **Memory:** No additional memory required

### Dependencies
- `numpy`: For FFT and array operations
- `audioop`: For audio format conversion

## Files Modified

- `backend/twilio_websocket_server.py:38-115`: Enhanced `has_significant_audio()` function
- `backend/twilio_websocket_server.py:332-338`: Added sustained speech counters
- `backend/twilio_websocket_server.py:434-488`: Integrated multi-layer filtering

## Testing Recommendations

1. **Test with TV on in background** - Should ignore TV audio
2. **Test with person far from phone** - Should reject distant speech
3. **Test with person close to phone** - Should accept clear speech
4. **Test with brief sounds** (coughs, door slams) - Should ignore
5. **Test with sustained conversation** - Should process correctly

## Future Enhancements

- **Adaptive thresholds:** Learn optimal thresholds per user
- **Voice fingerprinting:** Only respond to registered senior's voice
- **Background noise profiling:** Learn and subtract ambient noise patterns
- **ML-based VAD:** Use neural network for more sophisticated detection

---

**Version:** 2.5
**Last Updated:** 2025-10-31
**Author:** AI Voice Agent Team
