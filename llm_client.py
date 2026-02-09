import requests
import json
import config
from logger import setup_logger

logger = setup_logger("LLMClient")

class LLMClient:
    def __init__(self):
        self.api_url = config.LLM_API_URL
        self.model = config.LLM_MODEL_NAME

    def get_market_sentiment(self, data_summary):
        """
        Send market data summary to LLM and get a sentiment bias.
        Expected data_summary: string describing technicals (e.g. "RSI is 25, Price is below lower BB")
        """
        prompt = f"""
        You are an expert day trader specializing in reversal strategies for US Indices (SPY, QQQ).
        Analyze the following technical data and provide a trading bias.
        
        Technical Data:
        {data_summary}
        
        Task:
        Determine if the market is likely to REVERSE UP (Bullish), REVERSE DOWN (Bearish), or CONTINUE (Neutral).
        Focus on "Left-Side" trading - catching the turn.
        
        Response Format:
        JSON with keys: "bias" (BULLISH/BEARISH/NEUTRAL), "confidence" (0-10), "reasoning" (short text).
        Do not output markdown code blocks, just the JSON string.
        """

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful AI trading assistant."},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "temperature": 0.2
        }

        try:
            logger.debug(f"Sending request to LLM: {self.model}")
            response = requests.post(f"{self.api_url}/chat/completions", json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                import re
                # Remove <think> blocks
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                
                # Cleanup markdown code blocks
                if "```json" in content:
                    content = content.replace("```json", "").replace("```", "")
                
                # Find first { and last }
                start = content.find('{')
                end = content.rfind('}')
                
                if start != -1 and end != -1:
                    content = content[start:end+1]
                
                parsed_content = json.loads(content)
                logger.info(f"LLM Response: {parsed_content}")
                return parsed_content
            else:
                logger.error(f"LLM API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"LLM Request Failed: {e}")
            if 'response' in locals():
                logger.error(f"Raw Response: {response.text}")
            return None
