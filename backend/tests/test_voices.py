"""
Test different Azure Neural Voices
Browse and listen to available voices
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.services.speech_service import SpeechService

# Popular English neural voices for healthcare/senior care
VOICES = {
    "1": {
        "name": "en-US-JennyNeural",
        "description": "Female, warm and friendly (Current default)",
        "personality": "Conversational, empathetic"
    },
    "2": {
        "name": "en-US-AriaNeural",
        "description": "Female, professional yet warm",
        "personality": "Clear, expressive"
    },
    "3": {
        "name": "en-US-GuyNeural",
        "description": "Male, calm and reassuring",
        "personality": "Steady, professional"
    },
    "4": {
        "name": "en-US-SaraNeural",
        "description": "Female, gentle and caring",
        "personality": "Soft, nurturing"
    },
    "5": {
        "name": "en-US-TonyNeural",
        "description": "Male, friendly and approachable",
        "personality": "Casual, warm"
    },
    "6": {
        "name": "en-US-NancyNeural",
        "description": "Female, professional newsreader style",
        "personality": "Clear, articulate"
    },
    "7": {
        "name": "en-US-DavisNeural",
        "description": "Male, authoritative but kind",
        "personality": "Strong, confident"
    },
    "8": {
        "name": "en-US-AmberNeural",
        "description": "Female, young and energetic",
        "personality": "Bright, enthusiastic"
    },
    "9": {
        "name": "en-US-AnaNeural",
        "description": "Female, child-friendly",
        "personality": "Gentle, patient"
    },
    "10": {
        "name": "en-US-AndrewNeural",
        "description": "Male, technical and precise",
        "personality": "Professional, clear"
    },
    "11": {
        "name": "en-US-AshleyNeural",
        "description": "Female, casual and friendly",
        "personality": "Relaxed, conversational"
    },
    "12": {
        "name": "en-US-BrandonNeural",
        "description": "Male, young professional",
        "personality": "Fresh, engaging"
    },
    "13": {
        "name": "en-US-ChristopherNeural",
        "description": "Male, mature and wise",
        "personality": "Experienced, trustworthy"
    },
    "14": {
        "name": "en-US-CoraNeural",
        "description": "Female, corporate professional",
        "personality": "Polished, efficient"
    },
    "15": {
        "name": "en-US-ElizabethNeural",
        "description": "Female, sophisticated",
        "personality": "Refined, elegant"
    },
    "16": {
        "name": "en-US-EricNeural",
        "description": "Male, informative",
        "personality": "Educational, clear"
    },
    "17": {
        "name": "en-US-JacobNeural",
        "description": "Male, youthful",
        "personality": "Energetic, modern"
    },
    "18": {
        "name": "en-US-JaneNeural",
        "description": "Female, corporate",
        "personality": "Business-like, competent"
    },
    "19": {
        "name": "en-US-JasonNeural",
        "description": "Male, casual",
        "personality": "Laid-back, friendly"
    },
    "20": {
        "name": "en-US-MichelleNeural",
        "description": "Female, caring and warm",
        "personality": "Nurturing, supportive"
    }
}

# Test phrase
TEST_PHRASE = "Hello! I'm calling to check in on you today. How are you feeling? Did you sleep well last night?"


def main():
    print("\n" + "="*70)
    print("🎙️  AZURE VOICE TESTING - Senior Health Monitoring")
    print("="*70)
    print("\nRecommended voices for senior care:")
    print("  - Warm and friendly")
    print("  - Clear pronunciation")
    print("  - Calm and reassuring\n")
    print("="*70)

    # Show all voices
    print("\nAVAILABLE VOICES:\n")
    for num, info in VOICES.items():
        print(f"{num:>2}. {info['name']}")
        print(f"    {info['description']}")
        print(f"    Personality: {info['personality']}\n")

    print("="*70)
    print("\nTest phrase:")
    print(f'  "{TEST_PHRASE}"')
    print("="*70)

    while True:
        print("\nOptions:")
        print("  [1-20]  - Test a specific voice")
        print("  'all'   - Test all voices sequentially")
        print("  'top'   - Test top 5 recommended voices")
        print("  'set X' - Update .env to use voice X")
        print("  'quit'  - Exit")

        choice = input("\nYour choice: ").strip().lower()

        if choice == 'quit':
            print("\n👋 Goodbye!\n")
            break

        elif choice == 'all':
            print("\n🔊 Testing all voices...")
            for num, info in VOICES.items():
                test_voice(info['name'], info['description'])
                input("\n  Press Enter for next voice...")

        elif choice == 'top':
            print("\n🔊 Testing top 5 recommended voices for senior care...")
            top_voices = ['1', '2', '4', '20', '3']  # Jenny, Aria, Sara, Michelle, Guy
            for num in top_voices:
                info = VOICES[num]
                test_voice(info['name'], info['description'])
                input("\n  Press Enter for next voice...")

        elif choice.startswith('set '):
            voice_num = choice.split()[1]
            if voice_num in VOICES:
                update_env_voice(VOICES[voice_num]['name'])
            else:
                print("❌ Invalid voice number")

        elif choice in VOICES:
            info = VOICES[choice]
            test_voice(info['name'], info['description'])

        else:
            print("❌ Invalid choice. Please try again.")


def test_voice(voice_name: str, description: str):
    """Test a specific voice"""
    print(f"\n{'='*70}")
    print(f"🎤 Testing: {voice_name}")
    print(f"   {description}")
    print(f"{'='*70}")

    try:
        # Initialize speech service with selected voice
        speech = SpeechService(
            speech_key=config.AZURE_SPEECH_KEY,
            speech_region=config.AZURE_SPEECH_REGION,
            voice_name=voice_name
        )

        # Synthesize and play
        print("🔊 Playing...")
        success = speech.synthesize_to_speaker(TEST_PHRASE)

        if success:
            print("✅ Playback complete")
        else:
            print("❌ Playback failed")

    except Exception as e:
        print(f"❌ Error: {e}")


def update_env_voice(voice_name: str):
    """Update .env file with selected voice"""
    env_path = Path(__file__).parent / '.env'

    try:
        with open(env_path, 'r') as f:
            lines = f.readlines()

        # Find and update SPEECH_VOICE_NAME line
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('SPEECH_VOICE_NAME='):
                lines[i] = f'SPEECH_VOICE_NAME={voice_name}\n'
                updated = True
                break

        # If not found, add it
        if not updated:
            lines.append(f'\n# Voice Configuration\nSPEECH_VOICE_NAME={voice_name}\n')

        # Write back
        with open(env_path, 'w') as f:
            f.writelines(lines)

        print(f"\n✅ Updated .env file!")
        print(f"   Voice set to: {voice_name}")
        print(f"   Restart the app to use the new voice.\n")

    except Exception as e:
        print(f"❌ Error updating .env: {e}")
        print(f"\nManually add this line to your .env file:")
        print(f"SPEECH_VOICE_NAME={voice_name}")


if __name__ == "__main__":
    main()
