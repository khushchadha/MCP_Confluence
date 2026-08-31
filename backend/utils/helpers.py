from pathlib import Path
from custom_logger import logger

def load_prompt(prompt_path) -> str:
    """
    Read and return text content from a .md prompt file.
    
    Args:
        prompt_path: Path to the markdown prompt file
        
    Returns:
        Content of the prompt file as a string
        
    Raises:
        FileNotFoundError: If the prompt file doesn't exist
    """
    prompt_path = Path(prompt_path)
    if not prompt_path.exists():
        logger.info(f"PROMPT_MISSING | path={prompt_path}")
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    
    return prompt_path.read_text(encoding="utf-8").strip()