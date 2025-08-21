"""
LLM provider with retry logic and error handling.
"""
import json
import time
import logging
import requests
from typing import Dict, Any, Optional
from flask import current_app

logger = logging.getLogger(__name__)


class LLMConnectionError(Exception):
    """Exception for LLM connection errors"""
    pass


class LLMProvider:
    """Wrapper for LLM API calls with retry logic"""
    
    def __init__(self):
        self.api_key = current_app.config.get('DEEPSEEK_API_KEY')
        self.api_url = current_app.config.get('DEEPSEEK_API_URL') 
        self.model = current_app.config.get('DEEPSEEK_MODEL_CHAT')
        
        if not self.api_key or not self.api_url:
            raise LLMConnectionError("DeepSeek API key or URL is not configured.")
    
    def call_llm(self, prompt: str, max_retries: int = 2, timeout: int = 120, 
                 require_json: bool = True) -> Dict[str, Any]:
        """
        Call LLM API with exponential backoff retry.
        
        Args:
            prompt: The prompt to send
            max_retries: Maximum number of retries (default: 2)
            timeout: Request timeout in seconds
            require_json: Whether to enforce JSON response format
            
        Returns:
            Parsed response content
            
        Raises:
            LLMConnectionError: If all retries fail
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        
        if require_json:
            payload["response_format"] = {"type": "json_object"}
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"LLM API call attempt {attempt + 1}/{max_retries + 1}")
                
                response = requests.post(
                    self.api_url, 
                    headers=headers, 
                    data=json.dumps(payload, ensure_ascii=False), 
                    timeout=timeout
                )
                response.raise_for_status()
                
                result = response.json()
                
                if "choices" not in result or not result["choices"]:
                    raise LLMConnectionError("Invalid response format from LLM API")
                
                content = result["choices"][0]["message"]["content"]
                
                # Parse JSON if required
                if require_json:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON on attempt {attempt + 1}: {e}")
                        if attempt < max_retries:
                            # Retry with modified prompt
                            payload["messages"][0]["content"] = prompt + "\n\n请确保返回有效的JSON格式。"
                            time.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        else:
                            raise LLMConnectionError(f"LLM returned invalid JSON: {e}")
                else:
                    return {"content": content}
                    
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"LLM API request failed on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    break
        
        raise LLMConnectionError(f"LLM API failed after {max_retries + 1} attempts. Last error: {last_error}")


def get_llm_provider() -> LLMProvider:
    """Get LLM provider instance"""
    return LLMProvider()