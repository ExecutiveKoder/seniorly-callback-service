"""
Twilio Service
Handles outbound calling with Media Streams for real-time Azure Speech integration
"""
from twilio.rest import Client
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class TwilioService:
    """Manages outbound calls through Twilio with Media Streams"""

    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        """
        Initialize Twilio Service

        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            phone_number: Twilio phone number for outbound calls
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.phone_number = phone_number
        self.client = Client(account_sid, auth_token)

        logger.info("Twilio Service initialized (outbound number suppressed)")

    def initiate_outbound_call(
        self,
        destination_phone: str,
        webhook_url: str,
        senior_name: str = "there"
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call with media streaming

        Args:
            destination_phone: Phone number to call
            webhook_url: URL for voice webhook (handles TwiML)
            senior_name: Name of the senior being called

        Returns:
            Dict with call details
        """
        try:
            logger.info("Initiating outbound call (destination and name suppressed)")

            call = self.client.calls.create(
                to=destination_phone,
                from_=self.phone_number,
                url=webhook_url,
                method='POST',
                status_callback=f"{webhook_url}/status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST'
            )

            logger.info(f"Call initiated - SID: {call.sid}")

            return {
                'success': True,
                'call_sid': call.sid,
                'status': call.status,
                'to': destination_phone,
                'from': self.phone_number,
                'senior_name': senior_name
            }

        except Exception as e:
            logger.error(f"Failed to initiate call: {e}")
            return {
                'success': False,
                'error': str(e),
                'to': destination_phone
            }

    def get_call_status(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the status of a call

        Args:
            call_sid: Twilio Call SID

        Returns:
            Dict with call status details
        """
        try:
            call = self.client.calls(call_sid).fetch()

            return {
                'success': True,
                'sid': call.sid,
                'status': call.status,
                'duration': call.duration,
                'from': call.from_,
                'to': call.to
            }

        except Exception as e:
            logger.error(f"Failed to get call status: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def end_call(self, call_sid: str) -> bool:
        """
        End an active call

        Args:
            call_sid: Twilio Call SID

        Returns:
            True if successful
        """
        try:
            call = self.client.calls(call_sid).update(status='completed')
            logger.info(f"Call ended: {call_sid}")
            return True

        except Exception as e:
            logger.error(f"Failed to end call: {e}")
            return False
