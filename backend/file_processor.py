import os
import re
import jieba
from typing import List, Dict, Any
import docx
import fitz  # PyMuPDF


class FileProcessor:
    """Handles file parsing, tokenization, and chunking."""

    CHUNK_SIZE = 512       # tokens per chunk
    CHUNK_OVERLAP = 64     # overlap tokens

    def __init__(self):
        jieba.initialize()

    def read_file(self, file_path: str) -> str:
        """Read file content based on extension."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.txt':
            return self._read_txt(file_path)
        elif ext == '.md':
            return self._read_txt(file_path)
        elif ext == '.cpp':
            return self._read_txt(file_path)
        elif ext == '.c':
            return self._read_txt(file_path)
        elif ext == '.h':
            return self._read_txt(file_path)
        elif ext == '.hpp':
            return self._read_txt(file_path)
        elif ext == '.py':
            return self._read_txt(file_path)
        elif ext == '.docx':
            return self._read_docx(file_path)
        elif ext == '.pdf':
            return self._read_pdf(file_path)
        else:
            # fallback: try as plain text
            try:
                return self._read_txt(file_path)
            except:
                raise ValueError(f"Unsupported file type: {ext}")

    def _read_txt(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    def _read_docx(self, file_path: str) -> str:
        doc = docx.Document(file_path)
        return '\n'.join([p.text for p in doc.paragraphs])

    def _read_pdf(self, file_path: str) -> str:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text using jieba for Chinese + whitespace split for code/English."""
        # For code, split by whitespace and punctuation
        # For Chinese text, use jieba
        tokens = []
        # Split text into segments: code blocks vs natural language
        segments = re.split(r'(```[\s\S]*?```|`[^`]+`)', text)
        for seg in segments:
            if seg.startswith('`'):
                # Code segment: simple tokenization
                tokens.extend(seg.split())
            else:
                # Natural language: use jieba + whitespace
                words = jieba.lcut(seg)
                tokens.extend(words)
        return tokens

    def count_tokens(self, text: str) -> int:
        """Count approximate token count."""
        return len(self.tokenize(text))

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Split text into overlapping chunks."""
        tokens = self.tokenize(text)
        chunks = []

        if not tokens:
            return chunks

        start = 0
        chunk_id = 0
        while start < len(tokens):
            end = min(start + self.CHUNK_SIZE, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = ''.join(chunk_tokens)

            # Try to find clean boundary (end of sentence/line)
            chunk_text_clean = self._clean_chunk_boundary(chunk_text)

            chunks.append({
                'id': chunk_id,
                'text': chunk_text_clean,
                'token_count': len(chunk_tokens),
                'start_pos': start,
                'end_pos': end
            })
            chunk_id += 1

            # Move start with overlap
            if end >= len(tokens):
                break
            start = end - self.CHUNK_OVERLAP

        return chunks

    def _clean_chunk_boundary(self, text: str) -> str:
        """Try to make chunk boundaries at sentence breaks for cleaner semantics."""
        # If chunk is short enough, return as-is
        if len(text) < self.CHUNK_SIZE * 2:
            return text
        # Try to cut at last sentence end
        for delimiter in ['。', '！', '？', '\n', '.', '!', '?']:
            last_idx = text.rfind(delimiter)
            if last_idx > len(text) * 0.5:  # only cut if past halfway
                return text[:last_idx + 1]
        return text

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """Full pipeline: read -> chunk -> return result."""
        raw_text = self.read_file(file_path)
        chunks = self.chunk_text(raw_text)
        file_name = os.path.basename(file_path)
        return {
            'file_name': file_name,
            'file_path': file_path,
            'total_tokens': self.count_tokens(raw_text),
            'chunk_count': len(chunks),
            'chunks': chunks
        }