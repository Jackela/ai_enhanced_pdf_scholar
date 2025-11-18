from src.services.rag.chunking_strategies import ParagraphChunker, SentenceChunker


def test_chunker_creates_chunks():
    text = "Sentence one. Sentence two."
    chunker = SentenceChunker()
    chunks = chunker.chunk(text)
    assert chunks and "text" in chunks[0]

    para_chunker = ParagraphChunker()
    para_chunks = para_chunker.chunk("para1\n\npara2")
    assert para_chunks and "text" in para_chunks[0]
