# test_agent.py — run this from your terminal: python test_agent.py

import requests

BASE_URL = "http://localhost:8001/api/v1"

test_questions = [
    # Vendor risk
    "Which vendors are at high risk?",

]

for question in test_questions:
    print(f"\n{'='*60}")
    print(f"Q: {question}")

    response = requests.post(
        f"{BASE_URL}/ask",
        json={"question": question, "show_cypher": True}
    )
    data = response.json()

    print(f"STATUS: {data['status']}")
    if data.get("cypher_query"):
        print(f"CYPHER:\n{data['cypher_query']}")
    print(f"ANSWER:\n{data['answer']}")
    print(f"RESULTS COUNT: {data.get('result_count', 0)}")