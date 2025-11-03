"""
Configuration management for Azure Voice Agent
Uses Azure Key Vault for secrets (HIPAA compliant)
Falls back to .env for non-secret configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Load environment variables from .env file (for non-secret config)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Initialize Key Vault client for secrets
KEY_VAULT_NAME = os.getenv('AZURE_KEY_VAULT_NAME', 'seniorly-secrets')
KEY_VAULT_URL = f"https://{KEY_VAULT_NAME}.vault.azure.net"

try:
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
    _key_vault_available = True
except Exception as e:
    print(f"Warning: Key Vault not available ({e}). Using fallback to .env")
    secret_client = None
    _key_vault_available = False

def get_secret(secret_name: str, fallback_env_var: str = None) -> str:
    """
    Get secret from Key Vault with fallback to environment variable.
    HIPAA compliant - secrets should be in Key Vault in production.
    """
    if _key_vault_available and secret_client:
        try:
            secret = secret_client.get_secret(secret_name)
            return secret.value.strip("'\"")
        except Exception as e:
            print(f"Warning: Could not get secret '{secret_name}' from Key Vault: {e}")

    # Fallback to environment variable (for local development only)
    if fallback_env_var:
        return os.getenv(fallback_env_var, '').strip("'\"")
    return ''


class Config:
    """Application configuration loaded from environment variables"""

    # Resource Group
    RESOURCE_GROUP = os.getenv('RESOURCE_GROUP', 'voice-agent-rg')
    REGION_MAIN = os.getenv('REGION_MAIN', 'eastus2')
    REGION_COSMOS = os.getenv('REGION_COSMOS', 'westus2')

    # Azure OpenAI (GPT-5-CHAT)
    AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5-chat')
    AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', '').strip("'")
    AZURE_OPENAI_KEY = get_secret('AzureOpenAIKey', 'AZURE_OPENAI_KEY')

    # Azure Speech Services
    AZURE_SPEECH_ENDPOINT = os.getenv('AZURE_SPEECH_ENDPOINT', '').strip('"')
    AZURE_SPEECH_KEY = get_secret('AzureSpeechKey', 'AZURE_SPEECH_KEY')
    AZURE_SPEECH_KEY2 = get_secret('AzureSpeechKey', 'AZURE_SPEECH_KEY2')  # Use primary key as fallback
    AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION', 'eastus2')

    # Azure AI Search
    AZURE_SEARCH_ENDPOINT = os.getenv('AZURE_SEARCH_ENDPOINT', '').strip("'")
    AZURE_SEARCH_KEY = get_secret('AzureSearchKey', 'AZURE_SEARCH_KEY')
    SEARCH_INDEX = os.getenv('SEARCH_INDEX', 'knowledge-base')

    # Azure Cosmos DB
    AZURE_COSMOS_ENDPOINT = os.getenv('AZURE_COSMOS_ENDPOINT', '').strip("'")
    AZURE_COSMOS_KEY = get_secret('AzureCosmosKey', 'AZURE_COSMOS_KEY')
    COSMOS_DATABASE = os.getenv('COSMOS_DATABASE', 'conversations')
    COSMOS_CONTAINER = os.getenv('COSMOS_CONTAINER', 'sessions')

    # Azure Redis Cache
    AZURE_REDIS_HOST = os.getenv('AZURE_REDIS_HOST', '').strip("'")
    AZURE_REDIS_KEY = get_secret('AzureRedisKey', 'AZURE_REDIS_KEY')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6380'))
    REDIS_SSL = os.getenv('REDIS_SSL', 'true').lower() == 'true'

    # Azure SQL Database (for analytics)
    AZURE_SQL_SERVER = os.getenv('AZURE_SQL_SERVER', '').strip("'")
    AZURE_SQL_DATABASE = os.getenv('AZURE_SQL_DATABASE', '').strip("'")
    AZURE_SQL_USERNAME = os.getenv('AZURE_SQL_USERNAME', '').strip("'")
    AZURE_SQL_PASSWORD = get_secret('AzureSQLPassword', 'AZURE_SQL_PASSWORD')

    # Azure Container Registry
    ACR_LOGIN_SERVER = os.getenv('ACR_LOGIN_SERVER', '').strip("'")
    ACR_USERNAME = os.getenv('ACR_USERNAME', '').strip("'")
    ACR_PASSWORD = get_secret('ACRPassword', 'ACR_PASSWORD')

    # Azure Communication Services
    ACS_CONNECTION_STRING = get_secret('AzureCommunicationString', 'ACS_CONNECTION_STRING')
    ACS_ENDPOINT = os.getenv('ACS_ENDPOINT', '').strip("'")
    PHONE_NUMBER = os.getenv('PHONE_NUMBER', 'pending')

    # AWS Connect (force us-east-1 to match Connect instance)
    AWS_REGION = 'us-east-1'  # Connect instance region, don't use os.getenv
    AWS_CONNECT_INSTANCE_ID = os.getenv('AWS_CONNECT_INSTANCE_ID', '').strip("'")
    AWS_CONNECT_INSTANCE_ARN = os.getenv('AWS_CONNECT_INSTANCE_ARN', '').strip("'")
    AWS_CONNECT_PHONE_NUMBER = os.getenv('AWS_CONNECT_PHONE_NUMBER', '').strip("'")
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '').strip("'")
    AWS_SECRET_ACCESS_KEY = get_secret('AWSSecretAccessKey', 'AWS_SECRET_ACCESS_KEY')

    # Twilio (Outbound calling with Media Streams)
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '').strip("'")
    TWILIO_AUTH_TOKEN = get_secret('TwilioAuthToken', 'TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '').strip("'")

    # Voice settings
    SPEECH_VOICE_NAME = os.getenv('SPEECH_VOICE_NAME', 'en-US-JennyNeural')
    SPEECH_LANGUAGE = os.getenv('SPEECH_LANGUAGE', 'en-US')

    @staticmethod
    def get_ai_name() -> str:
        """Extract AI name from voice setting"""
        # First check if AGENT_NAME is explicitly set
        explicit_name = os.getenv('AGENT_NAME', '').strip()
        if explicit_name:
            return explicit_name

        # Otherwise extract from voice name
        voice_name = Config.SPEECH_VOICE_NAME

        # Extract the name from the voice (e.g., "en-US-JasonNeural" -> "Jason")
        if 'Jason' in voice_name:
            return 'Jason'
        elif 'Jenny' in voice_name:
            return 'Jenny'
        elif 'Sara' in voice_name:
            return 'Sara'
        elif 'Guy' in voice_name:
            return 'Guy'
        elif 'Aria' in voice_name:
            return 'Aria'
        elif 'Ava' in voice_name:
            return 'Ava'
        elif 'Davis' in voice_name:
            return 'Davis'
        elif 'Jane' in voice_name:
            return 'Jane'
        elif 'Nancy' in voice_name:
            return 'Nancy'
        elif 'Tony' in voice_name:
            return 'Tony'
        elif 'Brian' in voice_name:
            return 'Brian'
        elif 'Emma' in voice_name:
            return 'Emma'
        elif 'Ryan' in voice_name:
            return 'Ryan'
        elif 'Michelle' in voice_name:
            return 'Michelle'
        elif 'Roger' in voice_name:
            return 'Roger'
        elif 'Steffan' in voice_name:
            return 'Steffan'
        elif 'AIGenerated' in voice_name:
            return 'Alex'  # Generic name for AI generated voices
        else:
            # Default fallback
            return 'Alex'

    # Application settings
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    @classmethod
    def validate(cls) -> bool:
        """Validate that all required configuration is present"""
        required_fields = [
            ('AZURE_OPENAI_KEY', cls.AZURE_OPENAI_KEY),
            ('AZURE_OPENAI_ENDPOINT', cls.AZURE_OPENAI_ENDPOINT),
            ('AZURE_SPEECH_KEY', cls.AZURE_SPEECH_KEY),
            ('AZURE_SPEECH_REGION', cls.AZURE_SPEECH_REGION),
            ('AZURE_COSMOS_ENDPOINT', cls.AZURE_COSMOS_ENDPOINT),
            ('AZURE_COSMOS_KEY', cls.AZURE_COSMOS_KEY),
            ('AZURE_REDIS_HOST', cls.AZURE_REDIS_HOST),
            ('AZURE_REDIS_KEY', cls.AZURE_REDIS_KEY),
        ]

        missing = []
        for field_name, field_value in required_fields:
            if not field_value or field_value == '':
                missing.append(field_name)

        if missing:
            print(f"ERROR: Missing required configuration: {', '.join(missing)}")
            return False

        return True

    @classmethod
    def print_config(cls):
        """Print configuration (with sensitive data masked)"""
        print("\n=== Configuration ===")
        print(f"Resource Group: {cls.RESOURCE_GROUP}")
        print(f"Main Region: {cls.REGION_MAIN}")
        print(f"Cosmos Region: {cls.REGION_COSMOS}")
        print(f"OpenAI Deployment: {cls.AZURE_OPENAI_DEPLOYMENT_NAME}")
        print(f"OpenAI Endpoint: {cls.AZURE_OPENAI_ENDPOINT[:50]}...")
        print(f"Speech Region: {cls.AZURE_SPEECH_REGION}")
        print(f"Speech Voice: {cls.SPEECH_VOICE_NAME}")
        print(f"Cosmos Database: {cls.COSMOS_DATABASE}")
        print(f"Cosmos Container: {cls.COSMOS_CONTAINER}")
        print(f"Search Index: {cls.SEARCH_INDEX}")
        masked_phone = (cls.PHONE_NUMBER[:-4].replace(cls.PHONE_NUMBER[:-4], "***") + cls.PHONE_NUMBER[-4:]) if cls.PHONE_NUMBER else ""
        print(f"Phone Number: {masked_phone}")
        print(f"Debug Mode: {cls.DEBUG}")
        print("====================\n")


# Create a singleton instance
config = Config()
