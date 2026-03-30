import os
from datetime import datetime
from azure.cosmos import CosmosClient, PartitionKey
from dotenv import load_dotenv
import uuid

# Load environment variables
load_dotenv()

class CosmosDBHelper:
    def __init__(self):
        """Initialize Cosmos DB connection"""
        self.connection_string = os.getenv("AZURE_COSMOS_DB_CONN")
        self.database_name = os.getenv("AZURE_COSMOS_DB", "db-1")
        self.container_name = os.getenv("AZURE_COSMOS_CONTAINER", "messages")
        
        if not self.connection_string:
            raise ValueError("AZURE_COSMOS_DB_CONN environment variable not set")
        
        # Initialize Cosmos DB client
        self.client = CosmosClient.from_connection_string(self.connection_string)
        self.database = self.client.get_database_client(self.database_name)
        self.container = self.database.get_container_client(self.container_name)
    
    def get_container_info(self):
        """Get container configuration info including partition key"""
        try:
            container_props = self.container.read()
            partition_keys = container_props.get('partitionKey', {})
            print(f"[OK] Container Info:")
            print(f"  Partition Key Paths: {partition_keys.get('paths', [])}")
            print(f"  Partition Key Kind: {partition_keys.get('kind', 'Hash')}")
            return container_props
        except Exception as e:
            print(f"[ERROR] Failed to get container info: {e}")
            raise
    
    def add_record(self,
                   user_id: str,
                   conversation_id: str, 
                   role: str, 
                   content: str) -> dict:
        """
        Add a record to the Cosmos DB container
        
        Args:
            user_id (str): User identifier. Default: 'default'
            conversation_id (str): Conversation identifier (partition key)
            role (str): Role of the sender (e.g., 'user', 'assistant')
            content (str): Message content
            record_id (str, optional): Custom record ID. If not provided, one will be auto-generated
        
        Returns:
            dict: The created item with all properties
        """
        try:
            # Generate ID if not provided

            record_id = str(uuid.uuid4())

            
            # Create record using only conversationId as partition key
            # This matches most Cosmos DB container configurations
            record = {
                "id": record_id ,
                "user_id": user_id,
                "conversationId": conversation_id,  # Partition key. This is the session id that comes from front end
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"[DEBUG] Adding record with id: {record_id}, conversationId: {conversation_id}")
            print(f"[DEBUG] Record: {record}")
            
            # Add to container
            created_item = self.container.create_item(body=record)
            print(f"[OK] Record added to Cosmos DB: {record_id}")
            return created_item
        
        except Exception as e:
            print(f"[ERROR] Failed to add record to Cosmos DB: {e}")
            print(f"[ERROR] Error type: {type(e).__name__}")
            print(f"[ERROR] Record details: {record}")
            # Don't raise - let caller decide what to do
            return None
    
    def get_conversation(self, user_id: str, conversation_id: str) -> list:
        """
        Retrieve all records for a specific conversation
        
        Args:
            user_id (str): User identifier (partition key)
            conversation_id (str): Conversation identifier
        
        Returns:
            list: List of records matching the conversation ID
        """
        try:
            query = "SELECT * FROM c WHERE c.conversationId = @conversation_id ORDER BY c.timestamp"
            items = list(self.container.query_items(
                query=query,
                parameters=[{"name": "@conversation_id", "value": conversation_id}],
                partition_key=user_id  # Optimized: single partition query
            ))
            return items
        
        except Exception as e:
            print(f"[ERROR] Failed to retrieve conversation: {e}")
            raise

    def get_last_messages(self, user_id: str, conversation_id: str) -> list:
        """
        Retrieve last 2 records for a specific conversation formatted as message history
        
        Args:
            user_id (str): User identifier (partition key)
            conversation_id (str): Conversation identifier
        
        Returns:
            list: List of message history dictionaries with 'role' and 'content' keys, 
                  ready to be sent to LLM. Returns empty list if conversation doesn't exist.
        """
        try:
            query = "SELECT TOP 2 * FROM c WHERE c.conversationId = @conversation_id ORDER BY c.timestamp desc"
            items = list(self.container.query_items(
                query=query,
                parameters=[{"name": "@conversation_id", "value": conversation_id}],
                partition_key=user_id  # Optimized: single partition query
            ))

            # Reverse to get chronological order (oldest first)
            items.reverse()
            
            # Format as message history for LLM (only role and content)
            history = [{"role": item.get("role"), "content": item.get("content")} for item in items]
            return history
        
        except Exception as e:
            print(f"[WARNING] Failed to retrieve conversation messages for {conversation_id}: {e}")
            return []

    def close(self):
        """Close the Cosmos DB client connection"""
        pass  # Azure Cosmos client handles connections automatically

    def get_user_all_conversations(self, user_id: str) -> list:
        """
        Retrieve all conversations for a user (analysis query)
        
        Args:
            user_id (str): User identifier
        
        Returns:
            list: List of all messages across all conversations for the user
        """
        try:
            query = "SELECT c.conversationId, c.role, c.content, c.timestamp FROM c ORDER BY c.timestamp"
            items = list(self.container.query_items(
                query=query,
                partition_key=user_id
            ))
            return items
        except Exception as e:
            print(f"[ERROR] Failed to retrieve user conversations: {e}")
            raise

    def get_user_message_count(self, user_id: str, conversation_id: str = None) -> int:
        """
        Get message count for analysis
        
        Args:
            user_id (str): User identifier
            conversation_id (str, optional): If provided, count for specific conversation; else all user messages
        
        Returns:
            int: Number of messages
        """
        try:
            if conversation_id:
                query = "SELECT VALUE COUNT(c) FROM c WHERE c.conversationId = @conversation_id"
                params = [{"name": "@conversation_id", "value": conversation_id}]
            else:
                query = "SELECT VALUE COUNT(c) FROM c"
                params = []
            
            result = self.container.query_items(query=query, parameters=params, partition_key=user_id)
            count = list(result)[0]
            return count
        except Exception as e:
            print(f"[ERROR] Failed to get message count: {e}")
            return 0


def get_conversation_history(user_id: str, conversation_id: str) -> list:
    """
    Convenience function to retrieve conversation history
    
    Args:
        user_id (str): User identifier (partition key)
        conversation_id (str): Conversation identifier
    
    Returns:
        list: List of records for the conversation
    """
    helper = CosmosDBHelper()
    try:
        return helper.get_conversation(user_id, conversation_id)
    finally:
        helper.close()


if __name__ == "__main__":
    # Example usage
    try:
        cosmos = CosmosDBHelper()
        
        # First, check container info
        print("\n--- Container Configuration ---")
        cosmos.get_container_info()
        
        # Add a test record (without specifying record_id so it auto-generates a unique one)
        print("\n--- Adding Test Record ---")
        
        # Retrieve conversation
        print("\n--- Retrieving Conversation ---")
        user_id = "user_123"  # Example user
        conversation_id = "conv_001"
        history = cosmos.get_conversation(user_id, conversation_id)
        print(f"Conversation history: {len(history)} messages found")
        for msg in history:
            print(f"  - {msg['role']}: {msg['content'][:50]}...")
        
        cosmos.close()
    except Exception as e:
        print(f"Error in example: {e}")
