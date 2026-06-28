import json
import re

def parse_model_json(raw: str) -> dict:
    """Parse a JSON object from a model response that may be fenched or wrapped in prose"""
    text = raw.strip()
    # strip ``` json ... ``` code fences if present
    text = re.sub(r"\A```(?:json)?\s*|\s*```\Z", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    
    if start != -1 and end >  start:
        text = text[start:end+1]
    return json.loads(text)
        
        
    

    