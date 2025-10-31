"""
Research Service
Finds health resources, nearby doctors, educational materials for seniors
Uses Azure AI Search and web search capabilities
"""
import os
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ResearchService:
    """Service to research health information and resources for seniors"""

    def __init__(self, region: str = 'CA'):
        """
        Initialize research service

        Args:
            region: 'CA' for Canada, 'US' for United States
        """
        self.region = region
        self.bing_api_key = os.getenv('AZURE_BING_SEARCH_KEY', '')
        self.bing_endpoint = "https://api.bing.microsoft.com/v7.0/search"

        # Google Places API (works in Canada)
        self.google_api_key = os.getenv('GOOGLE_PLACES_API_KEY', '')
        self.google_places_endpoint = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    def search_nearby_doctors(self, condition: str, location: str, specialty: str = None) -> List[Dict]:
        """
        Search for nearby doctors and specialists

        Args:
            condition: Health condition (e.g., "diabetes", "arthritis")
            location: City/ZIP code or city name (e.g., "Toronto, ON", "M5V 3A8")
            specialty: Optional specialty (e.g., "endocrinologist", "cardiologist")

        Returns:
            List of doctor/clinic information
        """
        try:
            if not specialty:
                # Map conditions to specialties
                specialty_map = {
                    'diabetes': 'endocrinologist',
                    'arthritis': 'rheumatologist',
                    'heart': 'cardiologist',
                    'copd': 'pulmonologist',
                    'hypertension': 'cardiologist',
                    'memory': 'neurologist',
                    'mental health': 'psychiatrist'
                }
                specialty = specialty_map.get(condition.lower(), 'general practitioner')

            # For Canada, try Google Places API first (better Canadian coverage)
            if self.region == 'CA' and self.google_api_key:
                results = self._google_places_search(f"{specialty} {location} Canada", place_type='doctor')
            # For US or fallback, use Bing
            elif self.bing_api_key:
                results = self._bing_search(f"{specialty} near {location}", result_type='local')
            else:
                # Fallback to generic results
                results = self._create_generic_doctor_results(specialty, location)

            return results[:5]  # Return top 5

        except Exception as e:
            logger.error(f"Error searching for doctors: {e}")
            return []

    def search_educational_resources(self, topic: str, senior_friendly: bool = True) -> List[Dict]:
        """
        Search for educational resources about health topics

        Args:
            topic: Health topic (e.g., "diabetes management", "fall prevention")
            senior_friendly: Filter for senior-appropriate resources

        Returns:
            List of educational resources
        """
        try:
            # Add senior-friendly terms to query
            query = f"{topic} for seniors" if senior_friendly else topic
            query += " educational resources trusted medical information"

            results = []

            # Use Bing Search if available
            if self.bing_api_key:
                results = self._bing_search(query, result_type='general')
            else:
                # Provide trusted default resources
                results = self._create_trusted_health_resources(topic)

            # Filter for trusted domains
            trusted_domains = [
                'nih.gov', 'cdc.gov', 'mayoclinic.org', 'clevelandclinic.org',
                'webmd.com', 'healthline.com', 'medlineplus.gov', 'aarp.org',
                'medicare.gov', 'nia.nih.gov'  # National Institute on Aging
            ]

            filtered = []
            for result in results:
                url = result.get('url', '').lower()
                if any(domain in url for domain in trusted_domains):
                    filtered.append(result)

            return filtered[:5] if filtered else results[:5]

        except Exception as e:
            logger.error(f"Error searching educational resources: {e}")
            return []

    def search_local_services(self, service_type: str, location: str) -> List[Dict]:
        """
        Search for local services (pharmacies, meal delivery, transportation)

        Args:
            service_type: Type of service (e.g., "pharmacy", "meal delivery", "senior center")
            location: City/ZIP code

        Returns:
            List of local services
        """
        try:
            query = f"{service_type} near {location} for seniors"

            if self.bing_api_key:
                results = self._bing_search(query, result_type='local')
            else:
                results = self._create_generic_service_results(service_type, location)

            return results[:5]

        except Exception as e:
            logger.error(f"Error searching local services: {e}")
            return []

    def _google_places_search(self, query: str, place_type: str = 'doctor') -> List[Dict]:
        """
        Search Google Places API (better for Canadian locations)

        Args:
            query: Search query
            place_type: Type of place ('doctor', 'pharmacy', etc.)

        Returns:
            List of place results
        """
        if not self.google_api_key:
            return []

        try:
            params = {
                'query': query,
                'key': self.google_api_key,
                'type': place_type
            }

            response = requests.get(self.google_places_endpoint, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            results = []

            if data.get('status') == 'OK' and 'results' in data:
                for item in data['results']:
                    results.append({
                        'title': item.get('name', ''),
                        'address': item.get('formatted_address', ''),
                        'rating': item.get('rating', 'N/A'),
                        'phone': 'Call for details',  # Need separate API call for phone
                        'url': f"https://www.google.com/maps/place/?q=place_id:{item.get('place_id', '')}",
                        'source': 'google_places'
                    })

            return results

        except Exception as e:
            logger.error(f"Google Places search error: {e}")
            return []

    def _bing_search(self, query: str, result_type: str = 'general') -> List[Dict]:
        """
        Perform Bing search

        Args:
            query: Search query
            result_type: 'general', 'local', or 'news'

        Returns:
            List of search results
        """
        if not self.bing_api_key:
            return []

        try:
            headers = {'Ocp-Apim-Subscription-Key': self.bing_api_key}
            params = {
                'q': query,
                'count': 10,
                'mkt': 'en-US',
                'responseFilter': 'Webpages' if result_type == 'general' else 'Places'
            }

            response = requests.get(self.bing_endpoint, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            results = []

            # Parse web results
            if 'webPages' in data and 'value' in data['webPages']:
                for item in data['webPages']['value']:
                    results.append({
                        'title': item.get('name', ''),
                        'url': item.get('url', ''),
                        'description': item.get('snippet', ''),
                        'source': 'bing'
                    })

            # Parse local results
            if 'places' in data and 'value' in data['places']:
                for item in data['places']['value']:
                    results.append({
                        'title': item.get('name', ''),
                        'address': item.get('address', {}).get('addressLocality', ''),
                        'phone': item.get('telephone', ''),
                        'url': item.get('url', ''),
                        'source': 'bing_local'
                    })

            return results

        except Exception as e:
            logger.error(f"Bing search error: {e}")
            return []

    def _create_trusted_health_resources(self, topic: str) -> List[Dict]:
        """Create list of trusted health resources for common topics"""
        topic_lower = topic.lower()

        # Canadian vs US resources
        if self.region == 'CA':
            resources = [
                {
                    'title': 'Health Canada - Healthy Aging',
                    'url': 'https://www.canada.ca/en/health-canada/topics/healthy-living/healthy-aging.html',
                    'description': 'Official Canadian government health information for seniors',
                    'source': 'trusted'
                },
                {
                    'title': 'Public Health Agency of Canada - Seniors',
                    'url': 'https://www.canada.ca/en/public-health/topics/seniors-aging.html',
                    'description': 'Public health resources for Canadian seniors',
                    'source': 'trusted'
                },
                {
                    'title': 'Canadian Centre on Substance Use and Addiction - Seniors',
                    'url': 'https://www.ccsa.ca/seniors-and-substance-use',
                    'description': 'Information on medication and substance use for older adults',
                    'source': 'trusted'
                }
            ]
        else:
            # US resources
            resources = [
                {
                    'title': 'NIH - National Institute on Aging',
                    'url': 'https://www.nia.nih.gov/',
                    'description': 'Trusted information on health and aging from the National Institutes of Health',
                    'source': 'trusted'
                },
                {
                    'title': 'CDC - Healthy Aging',
                    'url': 'https://www.cdc.gov/aging/',
                    'description': 'Centers for Disease Control resources for healthy aging',
                    'source': 'trusted'
                },
                {
                    'title': 'MedlinePlus - Senior Health',
                    'url': 'https://medlineplus.gov/seniorhealth.html',
                    'description': 'Easy-to-read health information for older adults',
                    'source': 'trusted'
                }
            ]

        # Topic-specific resources
        if 'diabetes' in topic_lower:
            resources.insert(0, {
                'title': 'American Diabetes Association - Seniors',
                'url': 'https://diabetes.org/diabetes/older-adults',
                'description': 'Diabetes management information for older adults',
                'source': 'trusted'
            })

        elif 'fall' in topic_lower or 'balance' in topic_lower:
            resources.insert(0, {
                'title': 'CDC - STEADI: Stopping Elderly Accidents, Deaths & Injuries',
                'url': 'https://www.cdc.gov/steadi/',
                'description': 'Fall prevention resources and exercises for older adults',
                'source': 'trusted'
            })

        elif 'medication' in topic_lower:
            resources.insert(0, {
                'title': 'FDA - Medicines and You: A Guide for Older Adults',
                'url': 'https://www.fda.gov/drugs/special-features/medicines-and-you-guide-older-adults',
                'description': 'Safe medication use for seniors',
                'source': 'trusted'
            })

        elif 'exercise' in topic_lower or 'activity' in topic_lower:
            resources.insert(0, {
                'title': 'NIH - Exercise and Physical Activity for Older Adults',
                'url': 'https://www.nia.nih.gov/health/exercise-and-physical-activity',
                'description': 'Safe exercises and activity guide for seniors',
                'source': 'trusted'
            })

        return resources

    def _create_generic_doctor_results(self, specialty: str, location: str) -> List[Dict]:
        """Create generic doctor search results (fallback)"""
        return [
            {
                'title': f'{specialty.title()} - {location}',
                'description': f'Search for "{specialty} near {location}" on Google or ask your primary care doctor for a referral.',
                'url': f'https://www.google.com/search?q={specialty}+near+{location}',
                'source': 'generic'
            }
        ]

    def _create_generic_service_results(self, service_type: str, location: str) -> List[Dict]:
        """Create generic service search results (fallback)"""
        return [
            {
                'title': f'{service_type.title()} - {location}',
                'description': f'Search for "{service_type} near {location}" or call 211 for local resources.',
                'url': f'https://www.google.com/search?q={service_type}+near+{location}',
                'source': 'generic'
            }
        ]

    def format_results_for_email(self, results: List[Dict], title: str) -> str:
        """
        Format search results for email

        Args:
            results: List of search results
            title: Email section title

        Returns:
            Formatted HTML or plain text
        """
        if not results:
            return f"<h3>{title}</h3><p>No results found.</p>"

        lines = [f"<h3>{title}</h3>", "<ul>"]

        for result in results:
            item_title = result.get('title', 'Untitled')
            item_url = result.get('url', '')
            item_desc = result.get('description', '')

            lines.append(f"<li>")
            lines.append(f"  <strong><a href='{item_url}'>{item_title}</a></strong>")
            if item_desc:
                lines.append(f"  <p>{item_desc}</p>")
            if result.get('address'):
                lines.append(f"  <p>Address: {result['address']}</p>")
            if result.get('phone'):
                lines.append(f"  <p>Phone: {result['phone']}</p>")
            lines.append(f"</li>")

        lines.append("</ul>")

        return "\n".join(lines)

    def format_results_for_speech(self, results: List[Dict]) -> str:
        """
        Format search results for speech (to read aloud)

        Args:
            results: List of search results

        Returns:
            Natural language summary
        """
        if not results:
            return "I couldn't find any results for that."

        if len(results) == 1:
            result = results[0]
            return f"I found {result['title']}. {result.get('description', '')}"

        summary = f"I found {len(results)} resources for you. "
        summary += f"The top result is {results[0]['title']}. "

        if len(results) > 1:
            summary += f"I'll also include {results[1]['title']} and a few others in the email."

        return summary
