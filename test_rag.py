import requests

def test_rag_query():
    url = "http://localhost:8000/search"
    
    payload = {
        "query": "deep learning",
        "limit": 5
        # Pas de similarity_threshold pour avoir tous les résultats
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_rag_query()