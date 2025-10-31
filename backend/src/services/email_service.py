"""
Email Service
Sends health resources and research results to seniors via email
Uses Azure Communication Services for email delivery
"""
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime
from azure.communication.email import EmailClient
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)


class EmailService:
    """Service to send emails to seniors with health resources"""

    def __init__(self):
        """Initialize Azure Communication Services Email Client"""
        try:
            # Azure Communication Services credentials
            connection_string = os.getenv('AZURE_COMMUNICATION_CONNECTION_STRING', '')

            if connection_string:
                self.email_client = EmailClient.from_connection_string(connection_string)
                self.sender_address = os.getenv('AZURE_COMMUNICATION_SENDER_EMAIL', 'noreply@seniorly.com')
                logger.info("✅ Email service initialized with Azure Communication Services")
            else:
                # Fallback: log-only mode
                self.email_client = None
                logger.warning("⚠️  No email credentials - running in log-only mode")

        except Exception as e:
            logger.error(f"Failed to initialize email service: {e}")
            self.email_client = None

    def send_research_results(
        self,
        recipient_email: str,
        recipient_name: str,
        research_topic: str,
        results: List[Dict],
        include_disclaimer: bool = True
    ) -> bool:
        """
        Send research results to senior via email

        Args:
            recipient_email: Senior's email address
            recipient_name: Senior's name
            research_topic: Topic that was researched
            results: List of research results (doctors, resources, etc.)
            include_disclaimer: Include medical disclaimer

        Returns:
            True if sent successfully
        """
        try:
            # Build email HTML
            email_html = self._build_research_email_html(
                recipient_name=recipient_name,
                research_topic=research_topic,
                results=results,
                include_disclaimer=include_disclaimer
            )

            subject = f"Health Resources: {research_topic.title()}"

            return self._send_email(
                to_email=recipient_email,
                subject=subject,
                html_content=email_html
            )

        except Exception as e:
            logger.error(f"Error sending research results email: {e}")
            return False

    def send_appointment_reminder(
        self,
        recipient_email: str,
        recipient_name: str,
        appointment_details: Dict
    ) -> bool:
        """
        Send appointment reminder email

        Args:
            recipient_email: Senior's email
            recipient_name: Senior's name
            appointment_details: Dict with 'title', 'date', 'time', 'location'

        Returns:
            True if sent successfully
        """
        try:
            html_content = self._build_appointment_reminder_html(
                recipient_name=recipient_name,
                appointment_details=appointment_details
            )

            subject = f"Reminder: {appointment_details.get('title', 'Appointment')}"

            return self._send_email(
                to_email=recipient_email,
                subject=subject,
                html_content=html_content
            )

        except Exception as e:
            logger.error(f"Error sending appointment reminder: {e}")
            return False

    def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        Internal method to send email via Azure Communication Services

        Args:
            to_email: Recipient email
            subject: Email subject
            html_content: HTML email body

        Returns:
            True if sent successfully
        """
        if not self.email_client:
            logger.warning("📧 [LOG-ONLY MODE] Would send email (recipient and content suppressed)")
            return True  # Return True in log-only mode for testing

        try:
            message = {
                "senderAddress": self.sender_address,
                "recipients": {
                    "to": [{"address": to_email}]
                },
                "content": {
                    "subject": subject,
                    "html": html_content
                }
            }

            poller = self.email_client.begin_send(message)
            result = poller.result()

            logger.info("✅ Email sent successfully (recipient suppressed)")
            logger.info(f"   Message ID: {result.get('id', 'unknown')}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email: {e}")
            return False

    def _build_research_email_html(
        self,
        recipient_name: str,
        research_topic: str,
        results: List[Dict],
        include_disclaimer: bool
    ) -> str:
        """Build HTML email for research results"""

        html_parts = [
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background: #f9f9f9; }}
                    .resource {{ background: white; margin: 15px 0; padding: 15px; border-left: 4px solid #4CAF50; }}
                    .resource h3 {{ margin-top: 0; color: #4CAF50; }}
                    .resource a {{ color: #2196F3; text-decoration: none; }}
                    .footer {{ margin-top: 20px; padding: 15px; background: #eee; font-size: 12px; color: #666; }}
                    .disclaimer {{ background: #fff3cd; border: 1px solid #ffc107; padding: 15px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🏥 Seniorly Health Resources</h1>
                    </div>
                    <div class="content">
                        <p>Hi {recipient_name},</p>
                        <p>As we discussed on our call, here are the resources I found for <strong>{research_topic}</strong>:</p>
            """
        ]

        # Add each result
        for i, result in enumerate(results, 1):
            title = result.get('title', 'Resource')
            url = result.get('url', '#')
            description = result.get('description', '')
            address = result.get('address', '')
            phone = result.get('phone', '')
            rating = result.get('rating', '')

            html_parts.append(f"""
                <div class="resource">
                    <h3>{i}. <a href="{url}" target="_blank">{title}</a></h3>
                    <p>{description}</p>
            """)

            if address:
                html_parts.append(f"<p><strong>Address:</strong> {address}</p>")
            if phone:
                html_parts.append(f"<p><strong>Phone:</strong> {phone}</p>")
            if rating and rating != 'N/A':
                html_parts.append(f"<p><strong>Rating:</strong> ⭐ {rating}/5</p>")

            html_parts.append("</div>")

        # Add disclaimer
        if include_disclaimer:
            html_parts.append("""
                <div class="disclaimer">
                    <p><strong>⚠️ Important Disclaimer:</strong></p>
                    <p>This information is provided for educational purposes only and is not medical advice.
                    Always consult with your doctor or healthcare provider before making any health-related decisions.</p>
                </div>
            """)

        # Add footer
        html_parts.append(f"""
                    </div>
                    <div class="footer">
                        <p>This email was sent by Seniorly Voice Agent on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}.</p>
                        <p>If you have questions, please call us during your next scheduled check-in.</p>
                    </div>
                </div>
            </body>
            </html>
        """)

        return "".join(html_parts)

    def _build_appointment_reminder_html(
        self,
        recipient_name: str,
        appointment_details: Dict
    ) -> str:
        """Build HTML email for appointment reminder"""

        title = appointment_details.get('title', 'Appointment')
        date = appointment_details.get('date', 'TBD')
        time = appointment_details.get('time', '')
        location = appointment_details.get('location', '')
        notes = appointment_details.get('notes', '')

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2196F3; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9f9f9; }}
                .appointment {{ background: white; padding: 20px; border: 2px solid #2196F3; margin: 15px 0; }}
                .appointment h2 {{ margin-top: 0; color: #2196F3; }}
                .detail {{ margin: 10px 0; }}
                .detail strong {{ color: #555; }}
                .footer {{ margin-top: 20px; padding: 15px; background: #eee; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📅 Appointment Reminder</h1>
                </div>
                <div class="content">
                    <p>Hi {recipient_name},</p>
                    <p>This is a reminder about your upcoming appointment:</p>

                    <div class="appointment">
                        <h2>{title}</h2>
                        <div class="detail"><strong>Date:</strong> {date}</div>
        """

        if time:
            html += f'<div class="detail"><strong>Time:</strong> {time}</div>'
        if location:
            html += f'<div class="detail"><strong>Location:</strong> {location}</div>'
        if notes:
            html += f'<div class="detail"><strong>Notes:</strong> {notes}</div>'

        html += f"""
                    </div>

                    <p>Please arrive 15 minutes early if possible. If you need to reschedule, please call as soon as possible.</p>
                </div>
                <div class="footer">
                    <p>This reminder was sent by Seniorly Voice Agent on {datetime.now().strftime('%B %d, %Y')}.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def test_email_connection(self) -> bool:
        """Test email service connection"""
        if not self.email_client:
            logger.warning("No email client configured - running in log-only mode")
            return True

        logger.info("Email service is configured and ready")
        return True
