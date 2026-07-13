import requests
res = requests.post('http://127.0.0.1:8000/search', json={'query_text': "okay, so does that HELP you remember what Fauxton is? What about the Fractal Architect? Don't look it up manually - the goal should be for omnimem to supply the info", 'limit': 100, 'max_distance': 0.95})
data = res.json()
knowledge = [r for r in data if r.get('metadata', {}).get('category') == 'knowledge']
for k in knowledge[:5]:
    print(k.get('metadata', {}).get('source'), "|", k.get('concept_name'), "|", k.get('text_content')[:100].replace('\n', ' '))
print(f"Total returned: {len(data)}, Knowledge returned: {len(knowledge)}")
