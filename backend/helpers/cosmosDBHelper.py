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


if __name__ == "__main__":
    # Example usage
    try:
        cosmos = CosmosDBHelper()
        
        # Add a test record
        print("\n--- Adding Test Record ---")
        test_user = "user_123"
        test_conv = "conv_001"
        cosmos.add_record(test_user, test_conv, "user", "Test message")
        
        # Retrieve conversation
        print("\n--- Retrieving Conversation ---")
        history = cosmos.get_conversation(test_user, test_conv)
        print(f"Conversation history: {len(history)} messages found")
        for msg in history:
            print(f"  - {msg['role']}: {msg['content'][:50]}...")
        
        cosmos.close()
    except Exception as e:
        print(f"Error in example: {e}")
