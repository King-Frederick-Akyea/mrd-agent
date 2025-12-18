from typing import List, Any

def require_multiple_sources(claims: List[Any], min_sources: int = 2) -> bool:
    """Ensure high-impact claims have multiple independent sources."""
    for claim in claims:
        if len(getattr(claim, 'data_sources', [])) < min_sources:
            return False
    return True
