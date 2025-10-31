"""
Identity Verification Service
Handles name and date of birth verification for senior authentication
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class IdentityVerificationService:
    """Handles identity verification for seniors using name and DOB"""

    def __init__(self):
        """Initialize the identity verification service"""
        logger.info("Identity Verification Service initialized")

    def verify_identity(self, senior_profile: Dict, spoken_name: str, spoken_dob: str) -> Dict:
        """
        Verify senior's identity using name and date of birth

        Args:
            senior_profile: Senior's profile from database
            spoken_name: Name spoken by the senior
            spoken_dob: Date of birth spoken by the senior

        Returns:
            Dict with verification results
        """
        try:
            # Verify name
            name_result = self._verify_name(senior_profile, spoken_name)

            # Verify date of birth
            dob_result = self._verify_date_of_birth(senior_profile, spoken_dob)

            # Overall verification
            overall_verified = name_result['verified'] and dob_result['verified']
            confidence_score = (name_result['confidence'] + dob_result['confidence']) / 2

            result = {
                'verified': overall_verified,
                'confidence_score': confidence_score,
                'name_verification': name_result,
                'dob_verification': dob_result,
                'timestamp': datetime.utcnow().isoformat()
            }

            if overall_verified:
                logger.info("Identity verified for senior (name suppressed)")
            else:
                logger.warning("Identity verification failed for senior (name suppressed)")

            return result

        except Exception as e:
            logger.error(f"Error during identity verification: {e}")
            return {
                'verified': False,
                'error': str(e),
                'confidence_score': 0.0,
                'timestamp': datetime.utcnow().isoformat()
            }

    def _verify_name(self, senior_profile: Dict, spoken_name: str) -> Dict:
        """
        Verify the spoken name against the profile

        Args:
            senior_profile: Senior's profile data
            spoken_name: Name spoken by the senior

        Returns:
            Dict with name verification results
        """
        try:
            profile_name = senior_profile.get('fullName', '').lower().strip()
            spoken_name_clean = self._clean_spoken_text(spoken_name)

            # Extract first and last names from profile
            profile_parts = profile_name.split()
            first_name = profile_parts[0] if profile_parts else ''
            last_name = profile_parts[-1] if len(profile_parts) > 1 else ''

            # Multiple verification strategies
            strategies = [
                self._exact_match(profile_name, spoken_name_clean),
                self._fuzzy_match(profile_name, spoken_name_clean),
                self._partial_name_match(first_name, last_name, spoken_name_clean),
                self._phonetic_match(profile_name, spoken_name_clean)
            ]

            # Get best match
            best_match = max(strategies, key=lambda x: x['confidence'])

            return {
                'verified': best_match['confidence'] >= 0.7,  # 70% threshold
                'confidence': best_match['confidence'],
                'method': best_match['method'],
                'profile_name': senior_profile.get('fullName'),
                'spoken_name': spoken_name,
                'details': best_match
            }

        except Exception as e:
            logger.error(f"Error verifying name: {e}")
            return {
                'verified': False,
                'confidence': 0.0,
                'error': str(e)
            }

    def _verify_date_of_birth(self, senior_profile: Dict, spoken_dob: str) -> Dict:
        """
        Verify the spoken date of birth against the profile

        Args:
            senior_profile: Senior's profile data
            spoken_dob: Date of birth spoken by the senior

        Returns:
            Dict with DOB verification results
        """
        try:
            # Try root level first, then personalInfo for backward compatibility
            profile_dob = senior_profile.get('dateOfBirth') or senior_profile.get('personalInfo', {}).get('dateOfBirth')
            if not profile_dob:
                return {
                    'verified': False,
                    'confidence': 0.0,
                    'error': 'No date of birth in profile'
                }

            # Parse spoken DOB
            parsed_dates = self._parse_spoken_date(spoken_dob)
            profile_date = self._parse_profile_date(profile_dob)

            if not profile_date:
                return {
                    'verified': False,
                    'confidence': 0.0,
                    'error': 'Could not parse profile date of birth'
                }

            # Check for matches
            best_match = {'confidence': 0.0, 'method': 'none'}

            for parsed_date in parsed_dates:
                if parsed_date:
                    match = self._compare_dates(profile_date, parsed_date)
                    if match['confidence'] > best_match['confidence']:
                        best_match = match

            return {
                'verified': best_match['confidence'] >= 0.8,  # 80% threshold for DOB
                'confidence': best_match['confidence'],
                'method': best_match['method'],
                'profile_dob': profile_dob,
                'spoken_dob': spoken_dob,
                'details': best_match
            }

        except Exception as e:
            logger.error(f"Error verifying date of birth: {e}")
            return {
                'verified': False,
                'confidence': 0.0,
                'error': str(e)
            }

    def _clean_spoken_text(self, text: str) -> str:
        """Clean and normalize spoken text"""
        if not text:
            return ''

        # Convert to lowercase and remove extra whitespace
        cleaned = text.lower().strip()

        # Remove common speech artifacts (but be careful with month names)
        artifacts = [' um ', ' uh ', ' ah ', ' you know ', ' like ']
        for artifact in artifacts:
            cleaned = cleaned.replace(artifact, ' ')

        # Remove artifacts at the beginning and end
        start_artifacts = ['um ', 'uh ', 'ah ']
        end_artifacts = [' um', ' uh', ' ah']

        for artifact in start_artifacts:
            if cleaned.startswith(artifact):
                cleaned = cleaned[len(artifact):]

        for artifact in end_artifacts:
            if cleaned.endswith(artifact):
                cleaned = cleaned[:-len(artifact)]

        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def _exact_match(self, profile_name: str, spoken_name: str) -> Dict:
        """Check for exact name match"""
        confidence = 1.0 if profile_name == spoken_name else 0.0
        return {
            'confidence': confidence,
            'method': 'exact_match',
            'details': f"Profile: '{profile_name}' vs Spoken: '{spoken_name}'"
        }

    def _fuzzy_match(self, profile_name: str, spoken_name: str) -> Dict:
        """Check for fuzzy string match"""
        similarity = SequenceMatcher(None, profile_name, spoken_name).ratio()
        return {
            'confidence': similarity,
            'method': 'fuzzy_match',
            'details': f"Similarity: {similarity:.2f}"
        }

    def _partial_name_match(self, first_name: str, last_name: str, spoken_name: str) -> Dict:
        """Check if first or last name is mentioned"""
        confidence = 0.0
        details = []

        if first_name and first_name in spoken_name:
            confidence += 0.5
            details.append(f"First name '{first_name}' found")

        if last_name and last_name in spoken_name:
            confidence += 0.5
            details.append(f"Last name '{last_name}' found")

        return {
            'confidence': min(confidence, 1.0),
            'method': 'partial_match',
            'details': '; '.join(details) if details else 'No partial matches'
        }

    def _phonetic_match(self, profile_name: str, spoken_name: str) -> Dict:
        """Basic phonetic matching for speech recognition errors"""
        # Simple phonetic substitutions common in speech recognition
        phonetic_subs = {
            'ph': 'f', 'th': 't', 'ck': 'k', 'gh': 'g',
            'c': 'k', 'z': 's', 'x': 'ks'
        }

        phonetic_profile = profile_name
        phonetic_spoken = spoken_name

        for original, replacement in phonetic_subs.items():
            phonetic_profile = phonetic_profile.replace(original, replacement)
            phonetic_spoken = phonetic_spoken.replace(original, replacement)

        similarity = SequenceMatcher(None, phonetic_profile, phonetic_spoken).ratio()

        return {
            'confidence': similarity * 0.9,  # Slightly lower confidence for phonetic
            'method': 'phonetic_match',
            'details': f"Phonetic similarity: {similarity:.2f}"
        }

    def _parse_spoken_date(self, spoken_date: str) -> list:
        """Parse various formats of spoken dates"""
        dates = []
        spoken_clean = self._clean_spoken_text(spoken_date)

        # Common date patterns - order matters!
        patterns = [
            # MM/DD/YYYY or MM-DD-YYYY (most reliable)
            r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})',
            # Month day, year (January 15, 1950)
            r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',
            # Month DD YYYY (January 15 1950)
            r'(\w+)\s+(\d{1,2})\s+(\d{4})',
            # DD Month YYYY (15 January 1950)
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',
            # Just month and year for partial matches
            r'(\w+)\s+(\d{4})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, spoken_clean)
            for match in matches:
                try:
                    parsed_date = self._convert_match_to_date(match)
                    if parsed_date:
                        dates.append(parsed_date)
                except:
                    continue

        return dates

    def _convert_match_to_date(self, match: tuple) -> Optional[Dict]:
        """Convert regex match to standardized date dict"""
        try:
            if len(match) < 2:
                return None

            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12,
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }

            # Handle different match lengths
            if len(match) == 2:
                # Month and year only
                part1, part2 = match
                if part1.lower() in month_names and part2.isdigit():
                    return {
                        'month': month_names[part1.lower()],
                        'day': None,  # No day specified
                        'year': int(part2)
                    }

            elif len(match) == 3:
                part1, part2, part3 = match

                # Check if first part is MM/DD/YYYY format
                if part1.isdigit() and part2.isdigit() and part3.isdigit():
                    # MM/DD/YYYY format
                    month = int(part1)
                    day = int(part2)
                    year = int(part3)
                    if 1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2024:
                        return {'month': month, 'day': day, 'year': year}

                # Check for month name patterns
                month = None
                day = None
                year = None

                for part in match:
                    if part.lower() in month_names:
                        month = month_names[part.lower()]
                    elif part.isdigit():
                        num = int(part)
                        if 1900 <= num <= 2024:  # Year
                            year = num
                        elif 1 <= num <= 31 and day is None:  # Day
                            day = num

                if month and year:
                    return {
                        'month': month,
                        'day': day,  # Might be None
                        'year': year
                    }

        except Exception as e:
            logger.debug(f"Error converting date match: {e}")

        return None

    def _parse_profile_date(self, profile_dob: str) -> Optional[Dict]:
        """Parse date from profile (expected to be in ISO format or similar)"""
        try:
            # Try ISO format first (YYYY-MM-DD)
            if '-' in profile_dob:
                parts = profile_dob.split('-')
                if len(parts) == 3:
                    return {
                        'year': int(parts[0]),
                        'month': int(parts[1]),
                        'day': int(parts[2])
                    }

            # Try MM/DD/YYYY format
            if '/' in profile_dob:
                parts = profile_dob.split('/')
                if len(parts) == 3:
                    return {
                        'month': int(parts[0]),
                        'day': int(parts[1]),
                        'year': int(parts[2])
                    }

        except Exception as e:
            logger.error(f"Error parsing profile date: {e}")

        return None

    def _compare_dates(self, profile_date: Dict, spoken_date: Dict) -> Dict:
        """Compare two date dictionaries"""
        confidence = 0.0
        details = []

        # Check year (most important)
        if profile_date.get('year') == spoken_date.get('year'):
            confidence += 0.5
            details.append("Year matches")

        # Check month
        if profile_date.get('month') == spoken_date.get('month'):
            confidence += 0.3
            details.append("Month matches")

        # Check day (only if both have day specified)
        profile_day = profile_date.get('day')
        spoken_day = spoken_date.get('day')

        if profile_day is not None and spoken_day is not None:
            if profile_day == spoken_day:
                confidence += 0.2
                details.append("Day matches")
        elif spoken_day is None:
            # If spoken date has no day, give partial credit for month/year match
            confidence += 0.1
            details.append("Day not specified (partial credit)")

        return {
            'confidence': confidence,
            'method': 'date_comparison',
            'details': '; '.join(details) if details else 'No date components match'
        }