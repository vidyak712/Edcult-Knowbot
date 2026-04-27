from backend.helpers.cosmosDBHelper import CosmosDBHelper

cosmos = CosmosDBHelper()
result = cosmos.add_record(
    conversation_id="conv_001",
    role="user",
    content="Your message here",
    user_id="user_001"
)
history = cosmos.get_conversation("conv_001")
