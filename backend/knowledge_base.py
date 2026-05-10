import os
import json
import pickle
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import faiss


class KnowledgeBase:
    """Manages vector embeddings, storage (FAISS), and retrieval."""

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
                 vector_store_path: str = None,
                 model: Optional[SentenceTransformer] = None):
        """
        Initialize with a sentence-transformers model.
        Default model supports 50+ languages including Chinese and English.
        
        Args:
            model_name: HuggingFace model name (used if no model is passed)
            vector_store_path: Path to store FAISS index and metadata
            model: Pre-loaded SentenceTransformer model (shared across assistants)
        """
        self.model_name = model_name
        self.vector_store_path = vector_store_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'data', 'vector_store'
        )
        os.makedirs(self.vector_store_path, exist_ok=True)

        # Use shared model if provided, otherwise load separately
        if model is not None:
            self.model = model
            print(f"Using shared embedding model: {model_name}")
        else:
            # Load embedding model
            print(f"Loading embedding model: {model_name}...")
            self.model = SentenceTransformer(model_name)
            print("Embedding model loaded.")

        # FAISS index and metadata
        self.index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []  # each entry: {id, text, file_name, chunk_id}
        self.dimension = self.model.get_sentence_embedding_dimension()

        # Try to load existing index
        self._load()

    def _get_index_path(self) -> str:
        return os.path.join(self.vector_store_path, 'faiss.index')

    def _get_metadata_path(self) -> str:
        return os.path.join(self.vector_store_path, 'metadata.pkl')

    def _save(self):
        """Save FAISS index and metadata to disk."""
        if self.index is not None:
            faiss.write_index(self.index, self._get_index_path())
        with open(self._get_metadata_path(), 'wb') as f:
            pickle.dump(self.metadata, f)

    def _load(self):
        """Load existing FAISS index and metadata from disk."""
        index_path = self._get_index_path()
        meta_path = self._get_metadata_path()
        if os.path.exists(index_path) and os.path.exists(meta_path):
            try:
                self.index = faiss.read_index(index_path)
                with open(meta_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                print(f"Loaded existing index with {len(self.metadata)} chunks.")
            except Exception as e:
                print(f"Failed to load existing index: {e}")
                self.index = None
                self.metadata = []

    def add_chunks(self, chunks: List[Dict[str, Any]], file_name: str):
        """
        Add a list of text chunks to the knowledge base.
        Each chunk: {id, text, token_count, ...}
        """
        if not chunks:
            return

        texts = [c['text'] for c in chunks]
        # Generate embeddings
        embeddings = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

        # Create FAISS index if not exists
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dimension)  # Inner Product = cosine similarity (since normalized)

        # Add to FAISS
        self.index.add(np.array(embeddings).astype('float32'))

        # Store metadata
        base_idx = len(self.metadata)
        for i, chunk in enumerate(chunks):
            self.metadata.append({
                'id': base_idx + i,
                'text': chunk['text'],
                'file_name': file_name,
                'chunk_id': chunk['id'],
                'token_count': chunk.get('token_count', 0)
            })

        self._save()
        print(f"Added {len(chunks)} chunks from '{file_name}' to the knowledge base.")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search the knowledge base for chunks most relevant to the query.
        Returns list of {text, file_name, score, ...}
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # Encode query
        query_embedding = self.model.encode([query], normalize_embeddings=True)
        query_embedding = np.array(query_embedding).astype('float32')

        # Search
        scores, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.metadata):
                meta = self.metadata[idx]
                results.append({
                    'text': meta['text'],
                    'file_name': meta['file_name'],
                    'score': float(score),
                    'chunk_id': meta['chunk_id']
                })

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        total_chunks = len(self.metadata)
        files = set(m['file_name'] for m in self.metadata)
        return {
            'total_chunks': total_chunks,
            'total_files': len(files),
            'files': list(files),
            'index_size': self.index.ntotal if self.index else 0
        }

    def clear(self):
        """Clear all data from the knowledge base."""
        self.index = None
        self.metadata = []
        # Remove files
        index_path = self._get_index_path()
        meta_path = self._get_metadata_path()
        if os.path.exists(index_path):
            os.remove(index_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        print("Knowledge base cleared.")