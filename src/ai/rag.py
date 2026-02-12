# src/ai/rag.py
"""
RAG (Retrieval-Augmented Generation) pour OpenSpartan Graph.

Utilise LanceDB comme base vectorielle locale pour indexer :
- Documentation API Halo (Grunt, SPNKr)
- Fichiers .ai/ du projet
- Code source annoté
- Documentation externe

Usage:
    from src.ai.rag import HaloKnowledgeBase, RAGConfig

    config = RAGConfig(persist_directory="data/rag")
    kb = HaloKnowledgeBase(config)

    # Indexer des sources
    kb.index_directory("docs/")
    kb.index_github_repo("https://github.com/dend/grunt")

    # Rechercher
    results = kb.search("Comment fonctionne l'authentification Spartan Token?")
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore

try:
    import lancedb

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    lancedb = None  # type: ignore


@dataclass
class RAGConfig:
    """Configuration du système RAG."""

    # Stockage
    persist_directory: str = "data/rag"
    table_name: str = "halo_knowledge"

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Recherche
    top_k: int = 5

    # Sources à indexer par défaut
    default_sources: list[str] = field(
        default_factory=lambda: [
            "docs/",
            ".ai/",
            "src/",
        ]
    )

    # Patterns de fichiers à inclure
    include_patterns: list[str] = field(
        default_factory=lambda: [
            "*.md",
            "*.py",
            "*.json",
            "*.txt",
        ]
    )

    # Patterns à exclure
    exclude_patterns: list[str] = field(
        default_factory=lambda: [
            "__pycache__",
            "*.pyc",
            ".git",
            "node_modules",
            "*.db",
            "*.parquet",
        ]
    )


@dataclass
class Document:
    """Un document indexé."""

    id: str
    content: str
    metadata: dict[str, Any]

    @classmethod
    def from_file(cls, path: Path, content: str) -> Document:
        """Crée un document à partir d'un fichier."""
        doc_id = hashlib.md5(f"{path}:{content[:100]}".encode()).hexdigest()

        return cls(
            id=doc_id,
            content=content,
            metadata={
                "source": str(path),
                "filename": path.name,
                "extension": path.suffix,
                "source_type": "file",
                "indexed_at": datetime.now().isoformat(),
            },
        )

    @classmethod
    def from_github(cls, url: str, path: str, content: str) -> Document:
        """Crée un document à partir de GitHub."""
        doc_id = hashlib.md5(f"{url}:{path}:{content[:100]}".encode()).hexdigest()

        return cls(
            id=doc_id,
            content=content,
            metadata={
                "source": f"{url}/{path}",
                "source_type": "github",
                "repo_url": url,
                "file_path": path,
                "indexed_at": datetime.now().isoformat(),
            },
        )


@dataclass
class SearchResult:
    """Résultat de recherche."""

    content: str
    source: str
    score: float
    metadata: dict[str, Any]


class TextChunker:
    """Découpe le texte en chunks pour indexation."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> list[str]:
        """Découpe le texte en chunks avec overlap."""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # Essayer de couper à une fin de phrase/paragraphe
            if end < len(text):
                # Chercher le dernier saut de ligne
                last_newline = text.rfind("\n", start, end)
                if last_newline > start + self.chunk_size // 2:
                    end = last_newline + 1
                else:
                    # Chercher le dernier point
                    last_period = text.rfind(". ", start, end)
                    if last_period > start + self.chunk_size // 2:
                        end = last_period + 2

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - self.overlap

        return chunks

    def chunk_code(self, code: str, language: str = "python") -> list[str]:
        """Découpe du code en chunks intelligents (par fonction/classe)."""
        if language == "python":
            return self._chunk_python(code)
        return self.chunk_text(code)

    def _chunk_python(self, code: str) -> list[str]:
        """Découpe du code Python par fonction/classe."""
        chunks = []
        current_chunk = []
        current_size = 0

        lines = code.split("\n")

        for line in lines:
            # Nouvelle définition de fonction ou classe
            if (
                re.match(r"^(def |class |async def )", line)
                and current_chunk
                and current_size > 100
            ):
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_size = 0

            current_chunk.append(line)
            current_size += len(line)

            # Chunk trop grand
            if current_size >= self.chunk_size:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_size = 0

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return [c for c in chunks if c.strip()]


class GitHubIndexer:
    """Indexe un repository GitHub."""

    # Fichiers à indexer
    INCLUDE_EXTENSIONS = {".md", ".py", ".ts", ".js", ".json", ".cs", ".txt"}

    # Fichiers à ignorer
    EXCLUDE_PATTERNS = {
        "node_modules",
        "__pycache__",
        ".git",
        "dist",
        "build",
        "package-lock.json",
        "yarn.lock",
        ".env",
    }

    def __init__(self, repo_url: str):
        """
        Args:
            repo_url: URL du repo (ex: https://github.com/dend/grunt)
        """
        self.repo_url = repo_url.rstrip("/")
        self._parse_repo_info()

    def _parse_repo_info(self) -> None:
        """Parse owner/repo depuis l'URL."""
        match = re.match(r"https://github\.com/([^/]+)/([^/]+)", self.repo_url)
        if not match:
            raise ValueError(f"URL GitHub invalide: {self.repo_url}")

        self.owner = match.group(1)
        self.repo = match.group(2)
        self.api_base = f"https://api.github.com/repos/{self.owner}/{self.repo}"

    def fetch_tree(self, branch: str = "master") -> list[dict]:
        """Récupère l'arbre des fichiers du repo."""
        if not HTTPX_AVAILABLE:
            raise ModuleNotFoundError(
                "Le module 'httpx' est requis pour indexer un repo GitHub. "
                "Installez-le avec: pip install httpx"
            )
        url = f"{self.api_base}/git/trees/{branch}?recursive=1"

        with httpx.Client() as client:
            resp = client.get(url, headers={"Accept": "application/vnd.github.v3+json"})
            resp.raise_for_status()
            data = resp.json()

        return [
            item
            for item in data.get("tree", [])
            if item["type"] == "blob" and self._should_include(item["path"])
        ]

    def _should_include(self, path: str) -> bool:
        """Vérifie si un fichier doit être indexé."""
        # Vérifier l'extension
        ext = Path(path).suffix.lower()
        if ext not in self.INCLUDE_EXTENSIONS:
            return False

        # Vérifier les patterns exclus
        return all(pattern not in path for pattern in self.EXCLUDE_PATTERNS)

    def fetch_file_content(self, path: str, branch: str = "master") -> str | None:
        """Récupère le contenu d'un fichier."""
        if not HTTPX_AVAILABLE:
            return None
        url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{branch}/{path}"

        try:
            with httpx.Client() as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.text
        except Exception:
            return None

    def fetch_all_documents(self, branch: str = "master") -> list[Document]:
        """Récupère tous les documents du repo."""
        documents = []
        tree = self.fetch_tree(branch)

        for item in tree:
            content = self.fetch_file_content(item["path"], branch)
            if content:
                doc = Document.from_github(self.repo_url, item["path"], content)
                documents.append(doc)

        return documents


class HaloKnowledgeBase:
    """
    Base de connaissances Halo avec RAG.

    Utilise LanceDB pour le stockage vectoriel local.
    """

    def __init__(self, config: RAGConfig | None = None):
        """
        Args:
            config: Configuration RAG. Si None, utilise les valeurs par défaut.
        """
        if not LANCEDB_AVAILABLE:
            raise ImportError(
                "LanceDB n'est pas installé. " "Installez-le avec: pip install lancedb"
            )

        self.config = config or RAGConfig()
        self.chunker = TextChunker(
            chunk_size=self.config.chunk_size, overlap=self.config.chunk_overlap
        )

        # Initialiser LanceDB
        persist_path = Path(self.config.persist_directory)
        persist_path.mkdir(parents=True, exist_ok=True)

        self.db = lancedb.connect(str(persist_path))

        # Créer ou ouvrir la table
        self._init_table()

        # Stats
        self._indexed_count = 0

    def _init_table(self) -> None:
        """Initialise la table LanceDB."""
        table_name = self.config.table_name

        if table_name in self.db.table_names():
            self.table = self.db.open_table(table_name)
        else:
            # Créer une table vide avec le schéma
            self.table = None

    def _ensure_table(self, data: list[dict]) -> None:
        """S'assure que la table existe et y ajoute les données."""
        table_name = self.config.table_name

        if self.table is None:
            # Créer la table avec les premières données
            self.table = self.db.create_table(table_name, data=data, mode="overwrite")
        else:
            # Ajouter à la table existante
            self.table.add(data)

    @property
    def document_count(self) -> int:
        """Nombre de documents indexés."""
        if self.table is None:
            return 0
        return self.table.count_rows()

    def index_file(self, path: Path | str) -> int:
        """
        Indexe un fichier.

        Returns:
            Nombre de chunks indexés.
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {path}")

        content = path.read_text(encoding="utf-8", errors="ignore")

        # Chunker selon le type
        if path.suffix == ".py":
            chunks = self.chunker.chunk_code(content, "python")
        else:
            chunks = self.chunker.chunk_text(content)

        # Préparer les données pour LanceDB (schéma unifié)
        records = []
        for i, chunk in enumerate(chunks):
            doc = Document.from_file(path, chunk)
            records.append(
                {
                    "id": f"{doc.id}_{i}",
                    "text": chunk,
                    "source": str(path),
                    "source_type": "file",
                    "file_path": str(path),  # Unifié avec GitHub
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "indexed_at": datetime.now().isoformat(),
                }
            )

        if records:
            self._ensure_table(records)

        self._indexed_count += len(chunks)
        return len(chunks)

    def index_directory(self, directory: Path | str, recursive: bool = True) -> dict[str, int]:
        """
        Indexe un répertoire.

        Returns:
            Dictionnaire {fichier: nb_chunks}
        """
        directory = Path(directory)
        results = {}

        if not directory.exists():
            raise FileNotFoundError(f"Répertoire non trouvé: {directory}")

        # Patterns de fichiers
        patterns = self.config.include_patterns

        for pattern in patterns:
            files = directory.rglob(pattern) if recursive else directory.glob(pattern)

            for file_path in files:
                # Vérifier exclusions
                if any(excl in str(file_path) for excl in self.config.exclude_patterns):
                    continue

                try:
                    chunks = self.index_file(file_path)
                    results[str(file_path)] = chunks
                except Exception as e:
                    print(f"Erreur indexation {file_path}: {e}")

        return results

    def index_github_repo(self, repo_url: str, branch: str = "master") -> dict[str, int]:
        """
        Indexe un repository GitHub.

        Args:
            repo_url: URL du repo (ex: https://github.com/dend/grunt)
            branch: Branche à indexer (master par défaut)

        Returns:
            Dictionnaire {fichier: nb_chunks}
        """
        indexer = GitHubIndexer(repo_url)
        documents = indexer.fetch_all_documents(branch)

        results = {}

        for doc in documents:
            # Chunker le contenu
            ext = Path(doc.metadata.get("file_path", "")).suffix
            if ext == ".py":
                chunks = self.chunker.chunk_code(doc.content, "python")
            else:
                chunks = self.chunker.chunk_text(doc.content)

            records = []
            for i, chunk in enumerate(chunks):
                records.append(
                    {
                        "id": f"{doc.id}_{i}",
                        "text": chunk,
                        "source": doc.metadata.get("source", ""),
                        "source_type": "github",
                        "file_path": doc.metadata.get("file_path", ""),  # Schéma unifié
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "indexed_at": datetime.now().isoformat(),
                    }
                )

            if records:
                self._ensure_table(records)

            results[doc.metadata.get("file_path", doc.id)] = len(chunks)

        return results

    def index_text(
        self,
        text: str,
        source: str = "manual",
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> int:
        """
        Indexe du texte brut.

        Returns:
            Nombre de chunks indexés.
        """
        chunks = self.chunker.chunk_text(text)

        records = []
        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(f"{source}:{i}:{chunk[:50]}".encode()).hexdigest()
            records.append(
                {
                    "id": chunk_id,
                    "text": chunk,
                    "source": source,
                    "source_type": "text",
                    "file_path": source,  # Schéma unifié
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "indexed_at": datetime.now().isoformat(),
                }
            )

        if records:
            self._ensure_table(records)

        return len(chunks)

    def search(
        self, query: str, top_k: int | None = None, source_type: str | None = None
    ) -> list[SearchResult]:
        """
        Recherche dans la base de connaissances.

        Utilise une recherche textuelle (substring matching) car LanceDB
        nécessite des embeddings pour la recherche vectorielle.

        Args:
            query: Question ou termes de recherche
            top_k: Nombre de résultats (défaut: config.top_k)
            source_type: Filtrer par type de source ('github', 'file', 'text')

        Returns:
            Liste de résultats triés par pertinence
        """
        if self.table is None:
            return []

        k = top_k or self.config.top_k

        # Récupérer toutes les données
        all_data = self.table.to_pandas()

        # Filtrer par type de source si spécifié
        if source_type and "source_type" in all_data.columns:
            all_data = all_data[all_data["source_type"] == source_type]

        # Recherche textuelle avec scoring basé sur les occurrences
        query_lower = query.lower()
        query_terms = query_lower.split()

        scores = []
        for idx, row in all_data.iterrows():
            text = str(row.get("text", "")).lower()

            # Calculer un score basé sur le nombre de termes trouvés
            term_matches = sum(1 for term in query_terms if term in text)

            # Bonus si la requête exacte est trouvée
            exact_match = 1.0 if query_lower in text else 0.0

            # Score final
            score = (term_matches / max(len(query_terms), 1)) * 0.7 + exact_match * 0.3

            if score > 0:
                scores.append((idx, score, row))

        # Trier par score décroissant
        scores.sort(key=lambda x: x[1], reverse=True)

        # Limiter aux top_k résultats
        search_results = []
        for _idx, score, row in scores[:k]:
            search_results.append(
                SearchResult(
                    content=row.get("text", ""),
                    source=row.get("source", "unknown"),
                    score=score,
                    metadata={
                        "source_type": row.get("source_type", ""),
                        "chunk_index": row.get("chunk_index", 0),
                        "indexed_at": row.get("indexed_at", ""),
                    },
                )
            )

        return search_results

    def search_by_source(
        self, query: str, source_type: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """
        Recherche filtrée par type de source.

        Args:
            source_type: "github", "file", "text"
        """
        return self.search(query, top_k=top_k, source_type=source_type)

    def get_context_for_prompt(
        self, query: str, max_tokens: int = 4000, include_sources: bool = True
    ) -> str:
        """
        Génère un contexte formaté pour un prompt LLM.

        Args:
            query: Question de l'utilisateur
            max_tokens: Limite approximative de tokens
            include_sources: Inclure les sources dans le contexte

        Returns:
            Contexte formaté prêt à être injecté dans un prompt
        """
        results = self.search(query, top_k=10)

        context_parts = []
        current_length = 0
        char_per_token = 4  # Approximation

        for result in results:
            chunk_length = len(result.content)

            if current_length + chunk_length > max_tokens * char_per_token:
                break

            if include_sources:
                source_info = f"\n[Source: {result.source}]\n"
                context_parts.append(source_info + result.content)
            else:
                context_parts.append(result.content)

            current_length += chunk_length

        return "\n\n---\n\n".join(context_parts)

    def clear(self) -> None:
        """Supprime tous les documents de la table."""
        table_name = self.config.table_name
        if table_name in self.db.table_names():
            self.db.drop_table(table_name)
        self.table = None
        self._indexed_count = 0

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques de la base."""
        return {
            "total_documents": self.document_count,
            "table_name": self.config.table_name,
            "persist_directory": self.config.persist_directory,
            "chunk_size": self.config.chunk_size,
            "backend": "lancedb",
        }

    def export_index_manifest(self, path: Path | str) -> None:
        """Exporte un manifest des documents indexés."""
        path = Path(path)

        if self.table is None:
            manifest = {
                "total_chunks": 0,
                "sources": {},
                "config": {
                    "chunk_size": self.config.chunk_size,
                    "chunk_overlap": self.config.chunk_overlap,
                },
                "exported_at": datetime.now().isoformat(),
            }
        else:
            # Récupérer tous les documents
            all_data = self.table.to_pandas()

            sources = {}
            for _, row in all_data.iterrows():
                source = row.get("source", "unknown")
                if source not in sources:
                    sources[source] = {
                        "count": 0,
                        "source_type": row.get("source_type", "unknown"),
                    }
                sources[source]["count"] += 1

            manifest = {
                "total_chunks": self.document_count,
                "sources": sources,
                "config": {
                    "chunk_size": self.config.chunk_size,
                    "chunk_overlap": self.config.chunk_overlap,
                },
                "exported_at": datetime.now().isoformat(),
            }

        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


# Fonction utilitaire pour usage rapide
def create_knowledge_base(
    persist_dir: str = "data/rag", index_defaults: bool = True
) -> HaloKnowledgeBase:
    """
    Crée une base de connaissances avec les sources par défaut.

    Args:
        persist_dir: Répertoire de persistance
        index_defaults: Indexer les sources par défaut (docs/, .ai/, etc.)

    Returns:
        Instance de HaloKnowledgeBase
    """
    config = RAGConfig(persist_directory=persist_dir)
    kb = HaloKnowledgeBase(config)

    if index_defaults:
        for source in config.default_sources:
            if Path(source).exists():
                try:
                    kb.index_directory(source)
                except Exception as e:
                    print(f"Erreur indexation {source}: {e}")

    return kb
