import json
import os
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

from sentence_transformers import SentenceTransformer

# Load the problematic model
print("Loading OrcaDB/gte-base-en-v1.5...")
model = SentenceTransformer("OrcaDB/gte-base-en-v1.5", trust_remote_code=True)
print(f"Model loaded. Max sequence length: {model.max_seq_length}")
print(f"Tokenizer max length: {model.tokenizer.model_max_length if hasattr(model, 'tokenizer') else 'N/A'}")

# Load papers
with open('results/author_papers.json', encoding='utf-8') as f:
    data = json.load(f)

author_id = 'author_05d4b046-8319-56cd-a216-425dff836a4f'
papers = data.get(author_id, [])

print(f'\nAuthor has {len(papers)} papers')

# Extract abstracts
abstracts = []
for paper in papers:
    abstract = paper.get('abstract', '')
    if abstract and isinstance(abstract, str) and len(abstract.strip()) > 0:
        title = paper.get('title', '')
        text = f"{title}. {abstract}".strip()
        abstracts.append(text)

print(f'Found {len(abstracts)} valid abstracts\n')

# Test each abstract
for i, abstract_text in enumerate(abstracts):
    print(f'Paper {i+1}: length={len(abstract_text)} chars', end='')
    try:
        # Try encoding
        embedding = model.encode(abstract_text, show_progress_bar=False)
        print(f' - OK (embedding shape: {embedding.shape})')
    except Exception as e:
        print(f' - FAILED')
        print(f'  Error: {e}')
        print(f'  Title: {abstracts[i][:100]}...')
        print(f'  Full text length: {len(abstract_text)}')
        # Try to find the issue
        tokens = model.tokenize([abstract_text])
        print(f'  Token count: {len(tokens["input_ids"][0]) if "input_ids" in tokens else "unknown"}')
        break
