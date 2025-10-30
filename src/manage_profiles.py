"""
Senior Profile Management CLI
Add, view, update, and manage senior profiles
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.services.profile_service import SeniorProfileService
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def main():
    """Main CLI interface"""
    print("\n" + "="*60)
    print("👥 SENIOR PROFILE MANAGEMENT")
    print("="*60 + "\n")

    # Initialize profile service
    profile_service = SeniorProfileService(
        endpoint=config.AZURE_COSMOS_ENDPOINT,
        key=config.AZURE_COSMOS_KEY,
        database_name=config.COSMOS_DATABASE
    )

    # Ensure container exists
    if not profile_service.container:
        print("📦 Creating seniors container...")
        if profile_service.create_container():
            print("✅ Seniors container created successfully\n")
        else:
            print("❌ Failed to create seniors container\n")
            return

    while True:
        print("\n" + "="*60)
        print("OPTIONS:")
        print("="*60)
        print("1. Add New Senior")
        print("2. View Senior Profile")
        print("3. List All Active Seniors")
        print("4. Search by Phone Number")
        print("5. Update Senior Profile")
        print("6. View Senior's Call History")
        print("7. Exit")
        print("="*60)

        choice = input("\nSelect option (1-7): ").strip()

        if choice == '1':
            add_senior(profile_service)
        elif choice == '2':
            view_senior(profile_service)
        elif choice == '3':
            list_seniors(profile_service)
        elif choice == '4':
            search_by_phone(profile_service)
        elif choice == '5':
            update_senior(profile_service)
        elif choice == '6':
            view_call_history(profile_service)
        elif choice == '7':
            print("\n👋 Goodbye!\n")
            break
        else:
            print("\n❌ Invalid option. Please try again.")


def add_senior(service: SeniorProfileService):
    """Add a new senior profile"""
    print("\n" + "="*60)
    print("➕ ADD NEW SENIOR")
    print("="*60)

    first_name = input("\nFirst Name: ").strip()
    last_name = input("Last Name: ").strip()
    phone_number = input("Phone Number (e.g., +1-555-123-4567): ").strip()
    date_of_birth = input("Date of Birth (YYYY-MM-DD, or press Enter to skip): ").strip() or None

    print("\n--- Emergency Contact ---")
    emergency_contact_name = input("Emergency Contact Name: ").strip() or None
    emergency_contact_phone = input("Emergency Contact Phone: ").strip() or None

    print("\n--- Medical Information (optional) ---")
    medical_conditions = input("Medical Conditions (comma-separated): ").strip()
    conditions_list = [c.strip() for c in medical_conditions.split(",")] if medical_conditions else []

    medications = input("Medications (comma-separated): ").strip()
    medications_list = []
    if medications:
        for med in medications.split(","):
            medications_list.append({"name": med.strip(), "dosage": "", "frequency": ""})

    pcp = input("Primary Care Physician: ").strip() or None
    notes = input("Notes: ").strip() or None

    try:
        senior_id = service.create_senior_profile(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            date_of_birth=date_of_birth,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            medical_conditions=conditions_list,
            medications=medications_list,
            primary_care_physician=pcp,
            notes=notes
        )

        print(f"\n✅ Senior profile created successfully!")
        print(f"📝 Senior ID: {senior_id}")
        print(f"👤 Name: {first_name} {last_name}")
        print(f"📞 Phone: {phone_number}")

    except Exception as e:
        print(f"\n❌ Error creating profile: {e}")


def view_senior(service: SeniorProfileService):
    """View a senior's profile"""
    print("\n" + "="*60)
    print("👁️  VIEW SENIOR PROFILE")
    print("="*60)

    senior_id = input("\nEnter Senior ID: ").strip()

    profile = service.get_senior_profile(senior_id)

    if not profile:
        print(f"\n❌ Senior not found: {senior_id}")
        return

    print("\n" + "="*60)
    print(f"📋 PROFILE: {profile['fullName']}")
    print("="*60)
    print(f"Senior ID: {profile['seniorId']}")
    print(f"Name: {profile['fullName']}")
    print(f"Phone: {profile['phoneNumber']}")
    print(f"Date of Birth: {profile.get('dateOfBirth', 'N/A')}")
    print(f"Age: {profile.get('age', 'N/A')}")
    print(f"Status: {profile['status']}")
    print(f"Enrolled: {profile['enrollmentDate']}")

    print("\n--- Emergency Contact ---")
    print(f"Name: {profile['emergencyContact'].get('name', 'N/A')}")
    print(f"Phone: {profile['emergencyContact'].get('phone', 'N/A')}")

    print("\n--- Medical Information ---")
    print(f"Conditions: {', '.join(profile['medicalInformation']['conditions']) or 'None'}")
    print(f"Medications: {len(profile['medicalInformation']['medications'])} listed")
    print(f"PCP: {profile['medicalInformation'].get('primaryCarePhysician', 'N/A')}")

    print("\n--- Call Statistics ---")
    print(f"Total Calls: {profile['callHistory']['totalCalls']}")
    print(f"Missed Calls: {profile['callHistory']['missedCalls']}")
    print(f"Last Call: {profile['callSchedule'].get('lastCallDate', 'Never')}")

    print("\n--- Safety Alerts ---")
    print(f"Total Alerts: {profile['safetyAlerts']['totalAlerts']}")
    print(f"Open Alerts: {len(profile['safetyAlerts']['openAlerts'])}")
    print(f"Last Alert: {profile['safetyAlerts'].get('lastAlertDate', 'None')}")

    if profile.get('notes'):
        print(f"\n--- Notes ---")
        print(profile['notes'])

    print("="*60)


def list_seniors(service: SeniorProfileService):
    """List all active seniors"""
    print("\n" + "="*60)
    print("📋 ACTIVE SENIORS")
    print("="*60 + "\n")

    seniors = service.list_seniors(status="active")

    if not seniors:
        print("No active seniors found.")
        return

    for i, senior in enumerate(seniors, 1):
        print(f"{i}. {senior['fullName']}")
        print(f"   ID: {senior['seniorId']}")
        print(f"   Phone: {senior['phoneNumber']}")
        print(f"   Calls: {senior['callHistory']['totalCalls']}")
        print(f"   Last Call: {senior['callSchedule'].get('lastCallDate', 'Never')}")
        print()

    print(f"Total: {len(seniors)} active seniors")


def search_by_phone(service: SeniorProfileService):
    """Search for a senior by phone number"""
    print("\n" + "="*60)
    print("🔍 SEARCH BY PHONE NUMBER")
    print("="*60)

    phone = input("\nEnter phone number: ").strip()

    profile = service.search_seniors_by_phone(phone)

    if not profile:
        print(f"\n❌ No senior found with phone number: {phone}")
        return

    print(f"\n✅ Found: {profile['fullName']}")
    print(f"Senior ID: {profile['seniorId']}")
    print(f"Status: {profile['status']}")
    print(f"Total Calls: {profile['callHistory']['totalCalls']}")


def update_senior(service: SeniorProfileService):
    """Update a senior's profile"""
    print("\n" + "="*60)
    print("✏️  UPDATE SENIOR PROFILE")
    print("="*60)

    senior_id = input("\nEnter Senior ID: ").strip()

    profile = service.get_senior_profile(senior_id)
    if not profile:
        print(f"\n❌ Senior not found: {senior_id}")
        return

    print(f"\nUpdating profile for: {profile['fullName']}")
    print("\nWhat would you like to update?")
    print("1. Phone Number")
    print("2. Emergency Contact")
    print("3. Status (active/inactive)")
    print("4. Notes")
    print("5. Cancel")

    choice = input("\nSelect (1-5): ").strip()

    updates = {}

    if choice == '1':
        new_phone = input("New phone number: ").strip()
        updates["phoneNumber"] = new_phone
    elif choice == '2':
        ec_name = input("Emergency Contact Name: ").strip()
        ec_phone = input("Emergency Contact Phone: ").strip()
        updates["emergencyContact"] = {"name": ec_name, "phone": ec_phone}
    elif choice == '3':
        new_status = input("New status (active/inactive/discharged): ").strip()
        updates["status"] = new_status
    elif choice == '4':
        new_notes = input("Notes: ").strip()
        updates["notes"] = new_notes
    elif choice == '5':
        print("Update cancelled.")
        return
    else:
        print("Invalid choice.")
        return

    if service.update_senior_profile(senior_id, updates):
        print("\n✅ Profile updated successfully!")
    else:
        print("\n❌ Failed to update profile")


def view_call_history(service: SeniorProfileService):
    """View a senior's call history"""
    print("\n" + "="*60)
    print("📞 CALL HISTORY")
    print("="*60)

    senior_id = input("\nEnter Senior ID: ").strip()

    profile = service.get_senior_profile(senior_id)
    if not profile:
        print(f"\n❌ Senior not found: {senior_id}")
        return

    print(f"\n📋 Call History for: {profile['fullName']}")
    print("="*60)

    sessions = profile['callHistory']['sessions']

    if not sessions:
        print("No call history yet.")
        return

    # Show last 10 sessions
    recent_sessions = sessions[-10:]

    for i, session in enumerate(reversed(recent_sessions), 1):
        print(f"\n{i}. Session ID: {session['sessionId']}")
        print(f"   Date: {session['date']}")
        print(f"   Completed: {'Yes' if session.get('completed') else 'No'}")
        if session.get('summary'):
            print(f"   Summary: {session['summary']}")

    print(f"\n\nTotal Calls: {profile['callHistory']['totalCalls']}")
    print(f"Showing most recent {len(recent_sessions)} calls")


if __name__ == "__main__":
    main()
