from datetime import datetime

def search_competitor(name: str):
    return {
        "name": name,
        "downloads": 100000,
        "revenue": 500000,
        "as_of": datetime.now().isoformat()
    }
