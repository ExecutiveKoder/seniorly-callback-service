#!/usr/bin/env python3
"""
Test script to directly test AWS Connect phone calling functionality
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.services.aws_connect_service import AWSConnectService

def test_phone_call():
    """Test the AWS Connect phone calling directly"""

    print("🧪 TESTING AWS CONNECT PHONE CALLING")
    print("="*60)

    phone_number = "289-324-2125"  # John Wick's number
    senior_name = "John Wick"

    print(f"📞 Testing call to: {phone_number}")
    print(f"👤 Senior: {senior_name}")
    print(f"📋 AWS Instance ID: {config.AWS_CONNECT_INSTANCE_ID}")
    print()

    try:
        # Initialize AWS Connect service
        connect_service = AWSConnectService(
            region=config.AWS_REGION,
            instance_id=config.AWS_CONNECT_INSTANCE_ID,
            access_key=config.AWS_ACCESS_KEY_ID,
            secret_key=config.AWS_SECRET_ACCESS_KEY,
            phone_number=config.AWS_CONNECT_PHONE_NUMBER
        )

        print("✅ AWS Connect service initialized")

        # Skip connection test since seniorly user doesn't have ListContactFlows permission
        # The start_outbound_voice_contact call will verify connectivity
        print("⏭️  Skipping connection test (not needed for outbound calls)")

        # Make the test call
        print(f"\n📞 Initiating call to {phone_number}...")
        print("⚠️  This will make a REAL phone call!")

        call_result = connect_service.initiate_outbound_call(
            destination_phone=phone_number,
            senior_name=senior_name
        )

        if call_result['success']:
            print(f"\n🎉 CALL INITIATED SUCCESSFULLY!")
            print(f"   Contact ID: {call_result['contact_id']}")
            print(f"   From: {config.AWS_CONNECT_PHONE_NUMBER}")
            print(f"   To: {phone_number}")
            print()
            print("📱 Your phone should be ringing now!")
            print("🔊 You should hear Jason's greeting message")
            print("✅ If you hear the greeting, the Contact Flow is working!")
            return True
        else:
            print(f"\n❌ CALL FAILED: {call_result.get('error')}")
            return False

    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_phone_call()
    if success:
        print(f"\n🏆 Phone call test PASSED!")
        print("The new Contact Flow and AWS Connect integration is working!")
    else:
        print(f"\n💔 Phone call test FAILED")
        print("Need to debug the AWS Connect setup")