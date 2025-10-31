"""
AWS Connect Service
Handles outbound calling and call management using Amazon Connect
"""
import boto3
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class AWSConnectService:
    """Manages outbound calls through Amazon Connect"""

    def __init__(self, region: str, instance_id: str, access_key: str, secret_key: str, phone_number: str):
        """
        Initialize AWS Connect Service

        Args:
            region: AWS region (e.g., 'us-east-1')
            instance_id: Connect instance ID
            access_key: AWS access key ID
            secret_key: AWS secret access key
            phone_number: Connect phone number for outbound calls
        """
        self.region = region
        self.instance_id = instance_id
        self.phone_number = phone_number

        # Initialize boto3 client with explicit session to override system credentials
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

        self.connect_client = session.client('connect')

        logger.info("AWS Connect Service initialized")

    def initiate_outbound_call(self, destination_phone: str, senior_name: str) -> Dict[str, Any]:
        """
        Initiate an outbound call to a senior

        Args:
            destination_phone: Senior's phone number (e.g., "289-324-2125")
            senior_name: Senior's name for logging

        Returns:
            Dict with call details and contact ID
        """
        try:
            # Format phone numbers (remove dashes, add +1)
            formatted_destination = self._format_phone_number(destination_phone)
            formatted_source = self._format_phone_number(self.phone_number)

            logger.info("Initiating outbound call (senior name suppressed)")

            # Get AI agent name from config
            from src.config import config
            ai_name = config.get_ai_name()

            # Start outbound voice contact
            response = self.connect_client.start_outbound_voice_contact(
                DestinationPhoneNumber=formatted_destination,
                ContactFlowId=self._get_default_contact_flow_id(),
                InstanceId=self.instance_id,
                SourcePhoneNumber=formatted_source,
                Attributes={
                    'senior_name': senior_name,
                    'ai_name': ai_name,
                    'call_purpose': 'daily_wellness_check',
                    'timestamp': datetime.utcnow().isoformat()
                }
            )

            contact_id = response['ContactId']
            logger.info(f"Call initiated successfully. Contact ID: {contact_id}")

            return {
                'success': True,
                'contact_id': contact_id,
                'destination_phone': formatted_destination,
                'source_phone': formatted_source,
                'senior_name': senior_name,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to initiate outbound call: {e}")
            return {
                'success': False,
                'error': str(e),
                'destination_phone': destination_phone,
                'senior_name': senior_name
            }

    def get_call_status(self, contact_id: str) -> Dict[str, Any]:
        """
        Get the current status of a call

        Args:
            contact_id: Contact ID from initiate_outbound_call

        Returns:
            Dict with call status information
        """
        try:
            response = self.connect_client.describe_contact(
                InstanceId=self.instance_id,
                ContactId=contact_id
            )

            contact = response['Contact']

            return {
                'success': True,
                'contact_id': contact_id,
                'state': contact.get('State'),
                'state_reason': contact.get('StateReason'),
                'connected_time': contact.get('ConnectedToAgentTimestamp'),
                'disconnect_time': contact.get('DisconnectTimestamp'),
                'duration': self._calculate_duration(contact)
            }

        except Exception as e:
            logger.error(f"Failed to get call status: {e}")
            return {
                'success': False,
                'error': str(e),
                'contact_id': contact_id
            }

    def end_call(self, contact_id: str) -> bool:
        """
        End an active call

        Args:
            contact_id: Contact ID of the call to end

        Returns:
            True if call ended successfully
        """
        try:
            self.connect_client.stop_contact(
                ContactId=contact_id,
                InstanceId=self.instance_id
            )

            logger.info(f"Call ended successfully: {contact_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to end call: {e}")
            return False

    def _format_phone_number(self, phone: str) -> str:
        """
        Format phone number for AWS Connect

        Args:
            phone: Phone number in various formats

        Returns:
            Phone number in E.164 format (+1XXXXXXXXXX)
        """
        # Remove all non-digit characters
        digits_only = ''.join(filter(str.isdigit, phone))

        # Add +1 if not present (assuming US/Canada numbers)
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"
        else:
            return phone  # Return as-is if already formatted

    def _get_default_contact_flow_id(self) -> str:
        """
        Get the AI Voice Agent contact flow ID for outbound calls
        Uses our custom contact flow specifically designed for AI voice agent
        """
        try:
            # First try to find our custom AI Voice Agent contact flow
            response = self.connect_client.list_contact_flows(
                InstanceId=self.instance_id,
                ContactFlowTypes=['CONTACT_FLOW']
            )

            # Look for our custom AI Voice Agent flow first
            for flow in response['ContactFlowSummaryList']:
                if 'AI Voice Agent' in flow['Name']:
                    logger.info(f"Using AI Voice Agent contact flow: {flow['Id']}")
                    return flow['Id']

            # Fall back to any simple/basic flow (avoid complex queue flows)
            for flow in response['ContactFlowSummaryList']:
                flow_name = flow['Name'].lower()
                if ('simple' in flow_name or 'basic' in flow_name or
                    'test' in flow_name or 'inbound' in flow_name):
                    logger.info(f"Using fallback contact flow: {flow['Id']} ({flow['Name']})")
                    return flow['Id']

            # Last resort: use the first available (but warn about it)
            if response['ContactFlowSummaryList']:
                flow_id = response['ContactFlowSummaryList'][0]['Id']
                flow_name = response['ContactFlowSummaryList'][0]['Name']
                logger.warning(f"Using first available contact flow: {flow_id} ({flow_name}) - may not work correctly")
                return flow_id

            raise Exception("No contact flows found")

        except Exception as e:
            logger.error(f"Failed to get contact flow ID: {e}")
            # Return the Seniorly Voice Agent Simple flow (with Polly TTS) as fallback
            logger.info("Using Seniorly Voice Agent Simple flow as fallback")
            return "ad8aab03-abc1-46bf-bae4-fdcb061bf27b"

    def _calculate_duration(self, contact: Dict) -> Optional[int]:
        """
        Calculate call duration in seconds

        Args:
            contact: Contact details from AWS Connect

        Returns:
            Duration in seconds or None
        """
        try:
            connected_time = contact.get('ConnectedToAgentTimestamp')
            disconnect_time = contact.get('DisconnectTimestamp')

            if connected_time and disconnect_time:
                duration = (disconnect_time - connected_time).total_seconds()
                return int(duration)

            return None

        except Exception as e:
            logger.warning(f"Could not calculate call duration: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test connection to AWS Connect

        Returns:
            True if connection is successful
        """
        try:
            # Try to list contact flows as a connectivity test
            response = self.connect_client.list_contact_flows(
                InstanceId=self.instance_id,
                MaxResults=1
            )

            logger.info("AWS Connect connection test successful")
            return True

        except Exception as e:
            logger.error(f"AWS Connect connection test failed: {e}")
            return False