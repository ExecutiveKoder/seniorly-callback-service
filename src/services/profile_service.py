"""
Senior Profile Management Service
Manages senior profiles, health history, and longitudinal data
"""
from azure.cosmos import CosmosClient, exceptions as cosmos_exceptions
from typing import Optional, Dict, List, Any
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class SeniorProfileService:
    """Manages senior profiles and health records in Cosmos DB"""

    def __init__(self, endpoint: str, key: str, database_name: str):
        """
        Initialize Senior Profile Service

        Args:
            endpoint: Cosmos DB endpoint URL
            key: Cosmos DB access key
            database_name: Database name
        """
        self.endpoint = endpoint
        self.database_name = database_name
        self.container_name = "seniors"  # Separate container for profiles

        # Initialize Cosmos client
        self.client = CosmosClient(endpoint, key)
        self.database = self.client.get_database_client(database_name)

        # Get or create seniors container
        try:
            self.container = self.database.get_container_client(self.container_name)
            logger.info(f"Connected to existing seniors container: {self.container_name}")
        except exceptions.CosmosResourceNotFoundError:
            logger.info(f"Seniors container not found, will need to be created")
            self.container = None

    def create_container(self):
        """Create the seniors container if it doesn't exist"""
        try:
            container = self.database.create_container(
                id=self.container_name,
                partition_key={"paths": ["/seniorId"], "kind": "Hash"}
            )
            self.container = container
            logger.info(f"Created seniors container: {self.container_name}")
            return True
        except exceptions.CosmosResourceExistsError:
            self.container = self.database.get_container_client(self.container_name)
            logger.info(f"Seniors container already exists")
            return True
        except Exception as e:
            logger.error(f"Error creating seniors container: {e}")
            return False

    def create_senior_profile(
        self,
        first_name: str,
        last_name: str,
        phone_number: str,
        date_of_birth: Optional[str] = None,
        emergency_contact_name: Optional[str] = None,
        emergency_contact_phone: Optional[str] = None,
        medical_conditions: Optional[List[str]] = None,
        medications: Optional[List[Dict[str, str]]] = None,
        primary_care_physician: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Create a new senior profile

        Args:
            first_name: Senior's first name
            last_name: Senior's last name
            phone_number: Primary phone number
            date_of_birth: Date of birth (YYYY-MM-DD)
            emergency_contact_name: Emergency contact name
            emergency_contact_phone: Emergency contact phone
            medical_conditions: List of medical conditions
            medications: List of medications with dosage info
            primary_care_physician: PCP name and contact
            notes: Additional notes
            metadata: Additional metadata

        Returns:
            Senior ID
        """
        if not self.container:
            raise Exception("Seniors container not initialized. Call create_container() first.")

        senior_id = str(uuid.uuid4())

        profile = {
            "id": senior_id,
            "seniorId": senior_id,  # Partition key
            "firstName": first_name,
            "lastName": last_name,
            "fullName": f"{first_name} {last_name}",
            "phoneNumber": phone_number,
            "dateOfBirth": date_of_birth,
            "age": self._calculate_age(date_of_birth) if date_of_birth else None,
            "emergencyContact": {
                "name": emergency_contact_name,
                "phone": emergency_contact_phone
            },
            "medicalInformation": {
                "conditions": medical_conditions or [],
                "medications": medications or [],
                "primaryCarePhysician": primary_care_physician,
                "allergies": []
            },
            "callSchedule": {
                "frequency": "daily",
                "preferredTime": "10:00 AM",
                "timezone": "America/New_York",
                "lastCallDate": None,
                "nextCallDate": None
            },
            "healthMetrics": {
                "baselineVitals": {},
                "recentVitals": [],
                "alerts": []
            },
            "cognitiveBaseline": {
                "assessmentDate": None,
                "memoryScore": None,
                "orientationScore": None,
                "languageScore": None,
                "executiveFunctionScore": None
            },
            "callHistory": {
                "totalCalls": 0,
                "missedCalls": 0,
                "lastSessionId": None,
                "sessions": []
            },
            "safetyAlerts": {
                "totalAlerts": 0,
                "lastAlertDate": None,
                "openAlerts": []
            },
            "status": "active",  # active, inactive, discharged
            "enrollmentDate": datetime.utcnow().isoformat(),
            "lastUpdated": datetime.utcnow().isoformat(),
            "notes": notes or "",
            "metadata": metadata or {}
        }

        try:
            self.container.create_item(body=profile)
            logger.info(f"Created senior profile: {senior_id} - {first_name} {last_name}")
            return senior_id
        except Exception as e:
            logger.error(f"Error creating senior profile: {e}")
            raise

    def get_senior_profile(self, senior_id: str) -> Optional[Dict]:
        """
        Retrieve a senior's profile

        Args:
            senior_id: Senior ID

        Returns:
            Profile data or None if not found
        """
        if not self.container:
            raise Exception("Seniors container not initialized")

        try:
            profile = self.container.read_item(item=senior_id, partition_key=senior_id)
            logger.info(f"Retrieved senior profile: {senior_id}")
            return profile
        except cosmos_exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Senior profile not found: {senior_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving senior profile: {e}")
            return None

    def update_senior_profile(self, senior_id: str, updates: Dict) -> bool:
        """
        Update a senior's profile

        Args:
            senior_id: Senior ID
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        if not self.container:
            raise Exception("Seniors container not initialized")

        try:
            profile = self.get_senior_profile(senior_id)
            if not profile:
                return False

            # Update fields
            for key, value in updates.items():
                if key not in ["id", "seniorId"]:  # Don't allow changing ID
                    profile[key] = value

            profile["lastUpdated"] = datetime.utcnow().isoformat()

            # Save updated profile
            self.container.replace_item(item=senior_id, body=profile)
            logger.info(f"Updated senior profile: {senior_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating senior profile: {e}")
            return False

    def add_call_record(self, senior_id: str, session_id: str, call_metadata: Dict) -> bool:
        """
        Add a call record to senior's profile

        Args:
            senior_id: Senior ID
            session_id: Conversation session ID
            call_metadata: Metadata about the call

        Returns:
            True if successful
        """
        try:
            profile = self.get_senior_profile(senior_id)
            if not profile:
                return False

            # Add to call history
            profile["callHistory"]["totalCalls"] += 1
            profile["callHistory"]["lastSessionId"] = session_id
            profile["callHistory"]["sessions"].append({
                "sessionId": session_id,
                "date": datetime.utcnow().isoformat(),
                "duration": call_metadata.get("duration"),
                "completed": call_metadata.get("completed", True),
                "summary": call_metadata.get("summary", "")
            })

            # Update last call date
            profile["callSchedule"]["lastCallDate"] = datetime.utcnow().isoformat()

            # Keep only last 100 sessions in array
            if len(profile["callHistory"]["sessions"]) > 100:
                profile["callHistory"]["sessions"] = profile["callHistory"]["sessions"][-100:]

            profile["lastUpdated"] = datetime.utcnow().isoformat()

            self.container.replace_item(item=senior_id, body=profile)
            logger.info(f"Added call record for senior: {senior_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding call record: {e}")
            return False

    def add_health_metric(
        self,
        senior_id: str,
        metric_type: str,
        value: Any,
        unit: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        Add a health metric reading (blood pressure, heart rate, etc.)

        Args:
            senior_id: Senior ID
            metric_type: Type of metric (bp_systolic, bp_diastolic, heart_rate, etc.)
            value: Metric value
            unit: Unit of measurement
            timestamp: Optional timestamp (defaults to now)

        Returns:
            True if successful
        """
        try:
            profile = self.get_senior_profile(senior_id)
            if not profile:
                return False

            metric_record = {
                "type": metric_type,
                "value": value,
                "unit": unit,
                "timestamp": timestamp or datetime.utcnow().isoformat()
            }

            profile["healthMetrics"]["recentVitals"].append(metric_record)

            # Keep only last 100 readings
            if len(profile["healthMetrics"]["recentVitals"]) > 100:
                profile["healthMetrics"]["recentVitals"] = profile["healthMetrics"]["recentVitals"][-100:]

            profile["lastUpdated"] = datetime.utcnow().isoformat()

            self.container.replace_item(item=senior_id, body=profile)
            logger.info(f"Added health metric for senior {senior_id}: {metric_type}={value}{unit}")
            return True

        except Exception as e:
            logger.error(f"Error adding health metric: {e}")
            return False

    def add_safety_alert(
        self,
        senior_id: str,
        alert_level: str,
        categories: List[str],
        session_id: str,
        description: str
    ) -> bool:
        """
        Add a safety alert to senior's profile

        Args:
            senior_id: Senior ID
            alert_level: Alert severity
            categories: Alert categories
            session_id: Session where alert occurred
            description: Description of alert

        Returns:
            True if successful
        """
        try:
            profile = self.get_senior_profile(senior_id)
            if not profile:
                return False

            alert = {
                "alertId": str(uuid.uuid4()),
                "level": alert_level,
                "categories": categories,
                "sessionId": session_id,
                "description": description,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "open",
                "resolvedDate": None
            }

            profile["safetyAlerts"]["totalAlerts"] += 1
            profile["safetyAlerts"]["lastAlertDate"] = datetime.utcnow().isoformat()
            profile["safetyAlerts"]["openAlerts"].append(alert)

            profile["lastUpdated"] = datetime.utcnow().isoformat()

            self.container.replace_item(item=senior_id, body=profile)
            logger.warning(f"Added safety alert for senior {senior_id}: {alert_level} - {categories}")
            return True

        except Exception as e:
            logger.error(f"Error adding safety alert: {e}")
            return False

    def list_seniors(
        self,
        status: str = "active",
        limit: int = 100
    ) -> List[Dict]:
        """
        List seniors by status

        Args:
            status: Filter by status (active, inactive, discharged)
            limit: Maximum number to return

        Returns:
            List of senior profiles
        """
        if not self.container:
            raise Exception("Seniors container not initialized")

        try:
            query = f"SELECT * FROM c WHERE c.status = @status ORDER BY c.fullName"
            parameters = [{"name": "@status", "value": status}]

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                max_item_count=limit,
                enable_cross_partition_query=True
            ))

            logger.info(f"Retrieved {len(items)} seniors with status: {status}")
            return items

        except Exception as e:
            logger.error(f"Error listing seniors: {e}")
            return []

    def search_seniors_by_phone(self, phone_number: str) -> Optional[Dict]:
        """
        Find senior by phone number

        Args:
            phone_number: Phone number to search

        Returns:
            Senior profile or None
        """
        if not self.container:
            raise Exception("Seniors container not initialized")

        try:
            query = "SELECT * FROM c WHERE c.phoneNumber = @phone"
            parameters = [{"name": "@phone", "value": phone_number}]

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))

            if items:
                return items[0]
            return None

        except Exception as e:
            logger.error(f"Error searching by phone: {e}")
            return None

    def _calculate_age(self, date_of_birth: str) -> Optional[int]:
        """Calculate age from date of birth (YYYY-MM-DD)"""
        try:
            from datetime import datetime
            dob = datetime.strptime(date_of_birth, "%Y-%m-%d")
            today = datetime.utcnow()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age
        except:
            return None
