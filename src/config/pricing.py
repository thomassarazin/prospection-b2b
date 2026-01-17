# Configuration des Coûts IA (Pricing Model)

# Tarifs par Million de Tokens (Input / Output)
PRICING_MODEL = {
    # Vision (Qwen3-VL-Instruct)
    "Qwen/Qwen3-VL-235B-A22B-Instruct": {
        "input": 0.20,
        "output": 1.20,
        "name": "Qwen3-VL-235B"
    },
    
    # Texte / Code (DeepSeek-V3.2)
    # Texte / Code (DeepSeek-V3.2)
    "deepseek-ai/DeepSeek-V3.2": {
        "input": 0.26,
        "output": 0.39,
        "cache_hit": 0.13,
        "name": "DeepSeek-V3.2"
    },
    "deepseek-ai/DeepSeek-V3": {
        "input": 0.26,
        "output": 0.39,
        "cache_hit": 0.13,
        "name": "DeepSeek-V3"
    },
    "Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo": {
        "input": 0.28,
        "output": 1.20,
        "cache_hit": 0.14,
        "name": "Qwen3-Coder-480B"
    }
}

def calculate_cost(model_id: str, prompt_tokens: int, completion_tokens: int, cache_hits: int = 0) -> float:
    """Calcule le coût exact d'un appel API."""
    pricing = PRICING_MODEL.get(model_id)
    if not pricing:
        return 0.0 # Safety default
    
    # Coût Input (Standard vs Cache)
    input_cost = ((prompt_tokens - cache_hits) * pricing["input"] / 1_000_000)
    cache_cost = (cache_hits * pricing.get("cache_hit", pricing["input"]) / 1_000_000)
    
    # Coût Output
    output_cost = (completion_tokens * pricing["output"] / 1_000_000)
    
    return round(input_cost + cache_cost + output_cost, 6)
