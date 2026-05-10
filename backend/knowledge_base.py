import os
import json
import pickle
import hashlib
from datetime import datetime
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
        self.file_metadata: Dict[str, Dict[str, Any]] = {}  # file_uuid -> file info
        self.chunk_metadata: List[Dict[str, Any]] = []  # chunk info with faiss_id
        self.next_faiss_id = 0  # Track next available FAISS ID
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
            pickle.dump({
                'file_metadata': self.file_metadata,
                'chunk_metadata': self.chunk_metadata
            }, f)

    def _load(self):
        """Load existing FAISS index and metadata from disk."""
        index_path = self._get_index_path()
        meta_path = self._get_metadata_path()
        if os.path.exists(index_path) and os.path.exists(meta_path):
            try:
                with open(meta_path, 'rb') as f:
                    loaded_data = pickle.load(f)

                # Check if old format (list) or new format (dict)
                if isinstance(loaded_data, list):
                    # Old format detected
                    print("⚠️  Old metadata format detected. Clearing knowledge base.")
                    print("   Please re-upload your files.")
                    self.clear()
                    return

                # New format
                self.file_metadata = loaded_data.get('file_metadata', {})
                self.chunk_metadata = loaded_data.get('chunk_metadata', [])
                self.index = faiss.read_index(index_path)

                # Reconstruct next_faiss_id
                if self.chunk_metadata:
                    self.next_faiss_id = max(c['faiss_id'] for c in self.chunk_metadata) + 1
                else:
                    self.next_faiss_id = 0

                print(f"Loaded KB: {len(self.file_metadata)} files, {len(self.chunk_metadata)} chunks")
            except Exception as e:
                print(f"Failed to load existing index: {e}")
                self.index = None
                self.file_metadata = {}
                self.chunk_metadata = []
                self.next_faiss_id = 0

    def add_chunks(self, chunks: List[Dict[str, Any]], file_uuid: str,
                   original_name: str, physical_path: str, file_size: int,
                   file_hash: str, total_tokens: int):
        """
        Add a list of text chunks to the knowledge base with file metadata.
        Each chunk: {id, text, token_count, ...}
        """
        if not chunks:
            return

        texts = [c['text'] for c in chunks]
        # Generate embeddings
        embeddings = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

        # Create FAISS index if not exists
        if self.index is None:
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dimension))

        # Assign FAISS IDs
        chunk_ids = list(range(self.next_faiss_id, self.next_faiss_id + len(chunks)))
        self.next_faiss_id += len(chunks)

        # Add to FAISS with explicit IDs
        self.index.add_with_ids(
            np.array(embeddings).astype('float32'),
            np.array(chunk_ids, dtype=np.int64)
        )

        # Store chunk metadata
        for i, chunk in enumerate(chunks):
            self.chunk_metadata.append({
                'faiss_id': chunk_ids[i],
                'text': chunk['text'],
                'file_uuid': file_uuid,
                'chunk_id': chunk['id'],
                'token_count': chunk.get('token_count', 0)
            })

        # Store file metadata
        self.file_metadata[file_uuid] = {
            'original_name': original_name,
            'physical_path': physical_path,
            'upload_date': datetime.now().isoformat(),
            'file_size': file_size,
            'file_hash': file_hash,
            'chunk_count': len(chunks),
            'total_tokens': total_tokens,
            'chunk_ids': chunk_ids
        }

        self._save()
        print(f"Added {len(chunks)} chunks from '{original_name}' to the knowledge base.")

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
        # Build lookup dict for chunk metadata by faiss_id
        chunk_lookup = {c['faiss_id']: c for c in self.chunk_metadata}

        for score, faiss_id in zip(scores[0], indices[0]):
            if faiss_id >= 0 and faiss_id in chunk_lookup:
                chunk = chunk_lookup[faiss_id]
                file_info = self.file_metadata.get(chunk['file_uuid'], {})
                results.append({
                    'text': chunk['text'],
                    'file_name': file_info.get('original_name', 'unknown'),
                    'score': float(score),
                    'chunk_id': chunk['chunk_id']
                })

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        total_chunks = len(self.chunk_metadata)
        total_tokens = sum(f['total_tokens'] for f in self.file_metadata.values())
        return {
            'total_chunks': total_chunks,
            'total_files': len(self.file_metadata),
            'total_tokens': total_tokens,
            'index_size': self.index.ntotal if self.index else 0,
            'files': [
                {
                    'file_uuid': uuid,
                    'original_name': info['original_name'],
                    'chunk_count': info['chunk_count']
                }
                for uuid, info in self.file_metadata.items()
            ]
        }

    def get_files(self) -> List[Dict[str, Any]]:
        """Get list of all files in the knowledge base."""
        return [
            {
                'file_uuid': uuid,
                'original_name': info['original_name'],
                'upload_date': info['upload_date'],
                'file_size': info['file_size'],
                'chunk_count': info['chunk_count'],
                'total_tokens': info['total_tokens']
            }
            for uuid, info in self.file_metadata.items()
        ]

    def delete_file(self, file_uuid: str):
        """Delete a specific file from the knowledge base."""
        if file_uuid not in self.file_metadata:
            raise ValueError(f"File {file_uuid} not found in knowledge base")

        file_info = self.file_metadata[file_uuid]
        chunk_ids = file_info['chunk_ids']

        # Remove from FAISS index
        if self.index is not None and chunk_ids:
            self.index.remove_ids(np.array(chunk_ids, dtype=np.int64))

        # Remove chunk metadata
        self.chunk_metadata = [
            c for c in self.chunk_metadata
            if c['faiss_id'] not in chunk_ids
        ]

        # Remove file metadata
        del self.file_metadata[file_uuid]

        # Delete physical file
        physical_path = file_info['physical_path']
        if os.path.exists(physical_path):
            os.remove(physical_path)
            print(f"Deleted physical file: {physical_path}")

        self._save()
        print(f"Deleted file '{file_info['original_name']}' from knowledge base.")

    def clear(self):
        """Clear all data from the knowledge base."""
        self.index = None
        self.file_metadata = {}
        self.chunk_metadata = []
        self.next_faiss_id = 0
        # Remove files
        index_path = self._get_index_path()
        meta_path = self._get_metadata_path()
        if os.path.exists(index_path):
            os.remove(index_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        print("Knowledge base cleared.")