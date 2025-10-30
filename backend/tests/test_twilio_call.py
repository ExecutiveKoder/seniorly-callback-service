#!/usr/bin/env python3
"""
Test Twilio outbound calling with real-time Azure Speech
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.services.twilio_service import TwilioService

def main():
    print("="*60)
    print("🎙️  TWILIO OUTBOUND CALL TEST")
    print("="*60)
    print(f"AI Agent: {config.get_ai_name()}")
    print(f"Voice: {config.SPEECH_VOICE_NAME}")
    print(f"From: {config.TWILIO_PHONE_NUMBER}")
    print("="*60)

    # Get destination phone number
    destination = input("\nEnter phone number to call (e.g., 289-324-2125): ").strip()

    if not destination:
        print("❌ No phone number provided")
        return

    # Format phone number
    destination = destination.replace("-", "").replace(" ", "")
    if not destination.startswith("+"):
        destination = f"+1{destination}"

    senior_name = "John Wick"  # You can make this dynamic

    print(f"\n📞 Calling {destination}...")
    print(f"👤 Senior: {senior_name}")
    print(f"\n⚠️  IMPORTANT: Make sure the WebSocket server is running!")
    print(f"   Run: python twilio_websocket_server.py")
    print(f"\n   And expose it with ngrok:")
    print(f"   ngrok http 5000")
    print(f"\n   Then update webhook_url below with your ngrok URL\n")

    # YOU NEED TO UPDATE THIS WITH YOUR NGROK URL
    webhook_url = input("Enter your ngrok URL (e.g., https://abc123.ngrok.io): ").strip()

    if not webhook_url:
        print("❌ No webhook URL provided")
        return

    webhook_url = f"{webhook_url}/voice"

    # Initialize Twilio service
    twilio_service = TwilioService(
        account_sid=config.TWILIO_ACCOUNT_SID,
        auth_token=config.TWILIO_AUTH_TOKEN,
        phone_number=config.TWILIO_PHONE_NUMBER
    )

    # Make the call
    result = twilio_service.initiate_outbound_call(
        destination_phone=destination,
        webhook_url=webhook_url,
        senior_name=senior_name
    )

    if result['success']:
        print(f"\n🎉 CALL INITIATED!")
        print(f"   Call SID: {result['call_sid']}")
        print(f"   Status: {result['status']}")
        print(f"\n📱 Your phone should ring shortly!")
        print(f"🔊 You'll hear {config.get_ai_name()}'s voice via Azure Speech Services")
    else:
        print(f"\n❌ CALL FAILED: {result['error']}")

if __name__ == "__main__":
    main()
