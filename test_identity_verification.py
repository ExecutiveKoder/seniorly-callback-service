#!/usr/bin/env python3
"""
Test Identity Verification
Test the name and DOB verification with John Wick's profile
"""
import sys
sys.path.append('src')

from services.identity_verification_service import IdentityVerificationService
from services.profile_service import SeniorProfileService
from config import config

def test_identity_verification():
    print("🧪 Testing Identity Verification Service")
    print("="*50)

    # Get John Wick's profile
    profile_service = SeniorProfileService(
        endpoint=config.AZURE_COSMOS_ENDPOINT,
        key=config.AZURE_COSMOS_KEY,
        database_name=config.COSMOS_DATABASE
    )

    print("📋 Loading John Wick's profile...")
    profile = profile_service.get_senior_by_phone("289-324-2125")

    if not profile:
        print("❌ Could not find John Wick's profile")
        return

    print(f"✅ Profile loaded:")
    print(f"   Name: {profile['fullName']}")
    print(f"   DOB: {profile['dateOfBirth']}")

    # Initialize verification service
    verification_service = IdentityVerificationService()

    # Test scenarios
    test_cases = [
        {
            'name': 'Perfect Match',
            'spoken_name': 'John Wick',
            'spoken_dob': 'December 31 1941'
        },
        {
            'name': 'Partial Name Match',
            'spoken_name': 'John',
            'spoken_dob': 'December 31 1941'
        },
        {
            'name': 'Different Date Format',
            'spoken_name': 'John Wick',
            'spoken_dob': '12/31/1941'
        },
        {
            'name': 'Fuzzy Name Match',
            'spoken_name': 'Jon Wick',  # Slight misspelling
            'spoken_dob': 'December 31 1941'
        },
        {
            'name': 'Wrong Name',
            'spoken_name': 'James Bond',
            'spoken_dob': 'December 31 1941'
        },
        {
            'name': 'Wrong DOB',
            'spoken_name': 'John Wick',
            'spoken_dob': 'January 1 1950'
        }
    ]

    print(f"\n🧪 Running {len(test_cases)} test cases...")
    print("="*50)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        print(f"   Input Name: '{test_case['spoken_name']}'")
        print(f"   Input DOB: '{test_case['spoken_dob']}'")

        result = verification_service.verify_identity(
            senior_profile=profile,
            spoken_name=test_case['spoken_name'],
            spoken_dob=test_case['spoken_dob']
        )

        status = "✅ PASS" if result['verified'] else "❌ FAIL"
        confidence = result.get('confidence_score', 0)

        print(f"   Result: {status} (Confidence: {confidence:.1%})")

        if not result['verified']:
            name_conf = result.get('name_verification', {}).get('confidence', 0)
            dob_conf = result.get('dob_verification', {}).get('confidence', 0)
            print(f"   Details: Name={name_conf:.1%}, DOB={dob_conf:.1%}")

    print("\n" + "="*50)
    print("🎯 Testing complete!")
    print("📝 Expected results:")
    print("   Tests 1-4: Should PASS (various correct formats)")
    print("   Tests 5-6: Should FAIL (incorrect information)")

if __name__ == "__main__":
    test_identity_verification()