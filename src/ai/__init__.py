# src/ai/__init__.py
"""
Module IA pour OpenSpartan Graph.

Composants:
- RAG: Retrieval-Augmented Generation avec ChromaDB
- Router: Routage multi-LLM (futur)
"""

from .rag import HaloKnowledgeBase, RAGConfig

__all__ = ["HaloKnowledgeBase", "RAGConfig"]
