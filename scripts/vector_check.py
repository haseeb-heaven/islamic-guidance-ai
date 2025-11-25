from pinecone import Pinecone
from dotenv import load_dotenv
import os
from sentence_transformers import SentenceTransformer

load_dotenv()

# Setup Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("islamic-guidance")

# ✅ Use SAME model as upload
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')

# Query
while True:
    query = input("Enter your query: ")

    if query.lower() == "exit":
        break

    elif query.lower() == "clear":
        os.system('cls')
        continue

    # Generate embedding (same way as upload)
    query_vector = model.encode(
        query,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    if query_vector is None:
        print("Failed to generate embedding for query.")
        continue	

    print("Query vector first 10 elements:", query_vector[:10])
    print("Query vector shape:", query_vector.shape)

    # Search
    search_results = index.query(
        vector=query_vector.tolist(),  # Convert to list
        top_k=10,
        include_metadata=True
    )

    # Display results
    MIN_SCORE = 0.50
    print(f"\n🔍 Query: {query}")
    print("=" * 70)

    for i, match in enumerate(search_results['matches'], 1):
        if match['score'] >= MIN_SCORE:
            emoji = "📖" if match['metadata']['source'] == 'quran' else "📚"
            print(f"\n{emoji} Result #{i} | Score: {match['score']:.4f}")
            print(f"   Source: {match['metadata']['source'].upper()}")
            print(f"   Text: {match['metadata']['text'][:150]}...")
            print(f"   URL: {match['metadata']['url']}")
        else:
            print(f"\n❌ Result #{i} | Score: {match['score']:.4f}")
            print(f"   Source: {match['metadata']['source'].upper()}")
            print(f"   Text: {match['metadata']['text'][:150]}...")
            print(f"   URL: {match['metadata']['url']}")
