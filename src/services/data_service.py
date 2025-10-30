"""
Data Services integration
Handles Cosmos DB, Redis Cache, and AI Search
"""
from azure.cosmos import CosmosClient, exceptions as cosmos_exceptions
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import redis
from typing import Optional, List, Dict, Any
import logging
import json
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class CosmosDBService:
    """Manages conversation storage in Azure Cosmos DB"""

    def __init__(self, endpoint: str, key: str, database_name: str, container_name: str):
        """
        Initialize Cosmos DB Service

        Args:
            endpoint: Cosmos DB endpoint URL
            key: Cosmos DB access key
            database_name: Database name
            container_name: Container name
        """
        self.endpoint = endpoint
        self.database_name = database_name
        self.container_name = container_name

        # Initialize Cosmos client
        self.client = CosmosClient(endpoint, key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

        logger.info(f"Cosmos DB Service initialized: {database_name}/{container_name}")

    def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a new conversation session

        Args:
            session_id: Optional session ID (will generate if not provided)

        Returns:
            Session ID
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        session_data = {
            "id": session_id,
            "sessionId": session_id,
            "createdAt": datetime.utcnow().isoformat(),
            "messages": [],
            "metadata": {}
        }

        try:
            self.container.create_item(body=session_data)
            logger.info(f"Created session: {session_id}")
            return session_id
        except cosmos_exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error creating session: {e}")
            raise

    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Add a message to a conversation session

        Args:
            session_id: Session ID
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Optional metadata
        """
        try:
            # Read the session
            session = self.container.read_item(item=session_id, partition_key=session_id)

            # Add message
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            session["messages"].append(message)
            session["updatedAt"] = datetime.utcnow().isoformat()

            # Update the session
            self.container.replace_item(item=session_id, body=session)
            logger.info(f"Added {role} message to session {session_id}")

        except cosmos_exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error adding message to session: {e}")
            raise

    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Retrieve a conversation session

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found
        """
        try:
            session = self.container.read_item(item=session_id, partition_key=session_id)
            logger.info(f"Retrieved session: {session_id}")
            return session
        except cosmos_exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Session not found: {session_id}")
            return None
        except cosmos_exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error retrieving session: {e}")
            return None

    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Get conversation history for a session

        Args:
            session_id: Session ID

        Returns:
            List of messages in format for OpenAI
        """
        session = self.get_session(session_id)
        if not session:
            return []

        return [{"role": msg["role"], "content": msg["content"]} for msg in session.get("messages", [])]


class RedisCacheService:
    """Manages session state and caching with Azure Redis"""

    def __init__(self, host: str, key: str, port: int = 6380, ssl: bool = True):
        """
        Initialize Redis Cache Service

        Args:
            host: Redis host
            key: Redis access key
            port: Redis port
            ssl: Use SSL connection
        """
        self.host = host
        self.port = port

        # Initialize Redis client with timeout
        self.client = redis.Redis(
            host=host,
            port=port,
            password=key,
            ssl=ssl,
            decode_responses=True,
            socket_connect_timeout=5,  # 5 second connection timeout
            socket_timeout=5  # 5 second operation timeout
        )

        logger.info(f"Redis Cache Service initialized: {host}:{port}")

    def set_session_state(self, session_id: str, state: Dict, ttl: int = 3600, senior_id: str = None):
        """
        Store session state in cache

        Args:
            session_id: Session ID
            state: State data dictionary
            ttl: Time to live in seconds (default: 1 hour)
            senior_id: Optional senior ID for key namespacing
        """
        try:
            # Use senior_id in key for better data isolation
            if senior_id:
                key = f"senior:{senior_id}:session:{session_id}"
            else:
                key = f"session:{session_id}"

            self.client.setex(key, ttl, json.dumps(state))
            logger.info(f"Set session state for {session_id} (senior: {senior_id}) with TTL {ttl}s")
        except Exception as e:
            logger.error(f"Error setting session state: {e}")
            raise

    def get_session_state(self, session_id: str, senior_id: str = None) -> Optional[Dict]:
        """
        Retrieve session state from cache

        Args:
            session_id: Session ID
            senior_id: Optional senior ID for key namespacing

        Returns:
            State data or None if not found
        """
        try:
            # Try with senior_id first if provided
            if senior_id:
                key = f"senior:{senior_id}:session:{session_id}"
                data = self.client.get(key)
                if data:
                    logger.info(f"Retrieved session state for {session_id} (senior: {senior_id})")
                    return json.loads(data)

            # Fallback to old key format for backwards compatibility
            key = f"session:{session_id}"
            data = self.client.get(key)
            if data:
                logger.info(f"Retrieved session state for {session_id}")
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting session state: {e}")
            return None

    def delete_session_state(self, session_id: str, senior_id: str = None):
        """
        Delete session state from cache

        Args:
            session_id: Session ID
            senior_id: Optional senior ID for key namespacing
        """
        try:
            # Delete both possible key formats
            if senior_id:
                key = f"senior:{senior_id}:session:{session_id}"
                self.client.delete(key)
                logger.info(f"Deleted session state for {session_id} (senior: {senior_id})")

            # Also delete old format for backwards compatibility
            key = f"session:{session_id}"
            self.client.delete(key)
            logger.info(f"Deleted session state for {session_id}")
        except Exception as e:
            logger.error(f"Error deleting session state: {e}")

    def ping(self) -> bool:
        """
        Test Redis connection

        Returns:
            True if connected, False otherwise
        """
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False


class AISearchService:
    """Manages knowledge base search with Azure AI Search"""

    def __init__(self, endpoint: str, key: str, index_name: str):
        """
        Initialize AI Search Service

        Args:
            endpoint: AI Search endpoint URL
            key: AI Search API key
            index_name: Search index name
        """
        self.endpoint = endpoint
        self.index_name = index_name

        # Initialize search client
        self.client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(key)
        )

        logger.info(f"AI Search Service initialized: {index_name}")

    def search(self, query: str, top: int = 3) -> List[Dict[str, Any]]:
        """
        Search the knowledge base

        Args:
            query: Search query
            top: Number of results to return

        Returns:
            List of search results
        """
        try:
            results = self.client.search(search_text=query, top=top)
            search_results = []

            for result in results:
                search_results.append({
                    "score": result.get("@search.score", 0),
                    "content": result
                })

            logger.info(f"Search returned {len(search_results)} results for query: {query[:50]}...")
            return search_results

        except Exception as e:
            logger.error(f"Error searching AI Search: {e}")
            return []

    def get_context_for_query(self, query: str, top: int = 3) -> str:
        """
        Search and format results as context for GPT

        Args:
            query: Search query
            top: Number of results to include

        Returns:
            Formatted context string
        """
        results = self.search(query, top)

        if not results:
            return "No relevant information found in knowledge base."

        context_parts = []
        for i, result in enumerate(results, 1):
            content = result.get("content", {})
            # Extract relevant fields (adjust based on your index schema)
            text = content.get("content", "") or content.get("text", "") or str(content)
            context_parts.append(f"[Source {i}] {text}")

        return "\n\n".join(context_parts)


class DataService:
    """Combined data service managing all data operations"""

    def __init__(
        self,
        cosmos_endpoint: str,
        cosmos_key: str,
        cosmos_database: str,
        cosmos_container: str,
        redis_host: str,
        redis_key: str,
        redis_port: int,
        redis_ssl: bool,
        search_endpoint: str,
        search_key: str,
        search_index: str
    ):
        """Initialize all data services"""
        self.cosmos = CosmosDBService(cosmos_endpoint, cosmos_key, cosmos_database, cosmos_container)
        self.redis = RedisCacheService(redis_host, redis_key, redis_port, redis_ssl)
        self.search = AISearchService(search_endpoint, search_key, search_index)

        logger.info("Data Service initialized (Cosmos DB + Redis + AI Search)")

    def test_connections(self) -> Dict[str, bool]:
        """
        Test all service connections

        Returns:
            Dictionary with service connection status
        """
        status = {
            "redis": False,
            "cosmos": False,
            "search": False
        }

        # Test Redis
        try:
            status["redis"] = self.redis.ping()
        except Exception as e:
            logger.error(f"Redis connection test failed: {e}")

        # Test Cosmos DB
        try:
            # Try to query the container
            list(self.cosmos.container.query_items(
                query="SELECT TOP 1 * FROM c",
                enable_cross_partition_query=True
            ))
            status["cosmos"] = True
        except Exception as e:
            logger.error(f"Cosmos DB connection test failed: {e}")

        # Test AI Search (search is optional, so don't fail if empty)
        try:
            self.search.search("test", top=1)
            status["search"] = True
        except Exception as e:
            logger.warning(f"AI Search connection test failed: {e}")

        return status
