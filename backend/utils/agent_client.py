from openai import AsyncAzureOpenAI
import os
from agents import set_default_openai_client, set_tracing_disabled
from custom_logger import logger


def get_agent_client():
    """
    Create and return a single AsyncAzureOpenAI client and model name.
    
    This centralizes creation so callers reuse the same client/config.
    Reads configuration from environment variables.
    
    Returns:
        tuple: (agent_client, model_name)
            - agent_client: AsyncAzureOpenAI instance
            - model_name: The deployment name for the model
    
    Environment Variables Required:
        - AZURE_OPENAI_GPT_4O_API_KEY: Your Azure OpenAI API key
        - AZURE_OPENAI_GPT_4O_API_VERSION: API version (e.g., "2024-02-15-preview")
        - AZURE_OPENAI_GPT_4O_ENDPOINT: Azure OpenAI endpoint URL
        - AZURE_OPENAI_GPT_4O_DEPLOYMENT_NAME: Deployment name for the model
    """
    # Validate environment variables
    required_vars = [
        "AZURE_OPENAI_GPT_4O_API_KEY",
        "AZURE_OPENAI_GPT_4O_API_VERSION",
        "AZURE_OPENAI_GPT_4O_ENDPOINT",
        "AZURE_OPENAI_GPT_4O_DEPLOYMENT_NAME"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.info(f"CONFIG_INVALID | missing={', '.join(missing_vars)}")
        raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")
    
    try:
        agent_client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_GPT_4O_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_GPT_4O_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_GPT_4O_ENDPOINT"),
            azure_deployment=os.getenv("AZURE_OPENAI_GPT_4O_DEPLOYMENT_NAME"),
        )

        model_name = os.getenv("AZURE_OPENAI_GPT_4O_DEPLOYMENT_NAME")

        # Set global defaults used by your agents
        set_default_openai_client(agent_client)
        set_tracing_disabled(True)

        logger.info(f"LLM_CLIENT_READY | model={model_name}")
        
        return agent_client, model_name
        
    except Exception as e:
        logger.info(f"LLM_CLIENT_FAILED | error={e}")
        raise