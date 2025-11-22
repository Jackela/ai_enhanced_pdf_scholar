from typing import Any

#!/usr/bin/env python3
"""
Check available LlamaIndex imports for Google GenAI
"""

def check_embeddings() -> None:
    """Check available embedding classes"""
    try:
        import llama_index.embeddings.google_genai as google_genai

        print("=== Google GenAI Embeddings Module ===")
        print("Available attributes:")
        for attr in dir(google_genai):
            if not attr.startswith('_'):
                print(f"  - {attr}")

        # Try common names
        common_names = [
            'GoogleGenerativeAIEmbedding',
            'GoogleEmbedding',
            'GenAIEmbedding',
            'GoogleGenAIEmbedding',
            'EmbeddingModel'
        ]

        print("\nTesting common class names:")
        for name in common_names:
            try:
                cls = getattr(google_genai, name, None)
                if cls:
                    print(f"  ✅ {name} - {cls}")
                else:
                    print(f"  ❌ {name} - Not found")
            except Exception as e:
                print(f"  ❌ {name} - Error: {e}")

    except Exception as e:
        print(f"Failed to import embeddings module: {e}")

def check_llms() -> None:
    """Check available LLM classes"""
    try:
        import llama_index.llms.google_genai as google_genai

        print("\n=== Google GenAI LLMs Module ===")
        print("Available attributes:")
        for attr in dir(google_genai):
            if not attr.startswith('_'):
                print(f"  - {attr}")

        # Try common names
        common_names = [
            'GoogleGenerativeAI',
            'GoogleLLM',
            'GenAI',
            'GoogleGenAI',
            'Gemini'
        ]

        print("\nTesting common class names:")
        for name in common_names:
            try:
                cls = getattr(google_genai, name, None)
                if cls:
                    print(f"  ✅ {name} - {cls}")
                else:
                    print(f"  ❌ {name} - Not found")
            except Exception as e:
                print(f"  ❌ {name} - Error: {e}")

    except Exception as e:
        print(f"Failed to import LLMs module: {e}")

if __name__ == "__main__":
    check_embeddings()
    check_llms()
