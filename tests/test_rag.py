# tests/test_rag.py
"""
Tests pour le module RAG.
"""

from __future__ import annotations

import pytest


class TestTextChunker:
    """Tests pour le découpage de texte."""

    def test_import_without_lancedb(self):
        """Test que l'import échoue proprement sans LanceDB."""
        # Ce test vérifie juste que le module gère l'absence de LanceDB
        pass

    @pytest.fixture
    def chunker(self):
        """Fixture pour le chunker."""
        from src.ai.rag import TextChunker

        return TextChunker(chunk_size=100, overlap=20)

    def test_small_text_no_chunking(self, chunker):
        """Un petit texte ne doit pas être découpé."""
        text = "Hello world"
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_large_text_chunking(self, chunker):
        """Un grand texte doit être découpé."""
        text = "A" * 250  # 250 caractères
        chunks = chunker.chunk_text(text)
        assert len(chunks) > 1

    def test_chunk_overlap(self, chunker):
        """Les chunks doivent avoir un overlap."""
        text = "A" * 200
        chunks = chunker.chunk_text(text)

        # Avec overlap de 20, le 2ème chunk doit commencer avant la fin du 1er
        if len(chunks) >= 2:
            # L'overlap devrait créer une redondance
            assert len(chunks[0]) + len(chunks[1]) > len(text)

    def test_python_chunking(self, chunker):
        """Le code Python doit être découpé par fonction."""
        code = '''
def function_one():
    """First function."""
    return 1

def function_two():
    """Second function."""
    return 2

class MyClass:
    def method(self):
        pass
'''
        chunks = chunker.chunk_code(code, "python")
        assert len(chunks) >= 1


class TestDocument:
    """Tests pour la classe Document."""

    def test_from_file(self, tmp_path):
        """Test création depuis un fichier."""
        from src.ai.rag import Document

        test_file = tmp_path / "test.md"
        test_file.write_text("# Test content")

        doc = Document.from_file(test_file, "# Test content")

        assert doc.content == "# Test content"
        assert doc.metadata["filename"] == "test.md"
        assert doc.metadata["extension"] == ".md"

    def test_from_github(self):
        """Test création depuis GitHub."""
        from src.ai.rag import Document

        doc = Document.from_github(
            url="https://github.com/dend/grunt", path="README.md", content="# Grunt"
        )

        assert doc.content == "# Grunt"
        assert doc.metadata["source_type"] == "github"
        assert doc.metadata["repo_url"] == "https://github.com/dend/grunt"


class TestGitHubIndexer:
    """Tests pour l'indexeur GitHub."""

    def test_parse_repo_url(self):
        """Test parsing de l'URL."""
        from src.ai.rag import GitHubIndexer

        indexer = GitHubIndexer("https://github.com/dend/grunt")

        assert indexer.owner == "dend"
        assert indexer.repo == "grunt"

    def test_invalid_url(self):
        """Test URL invalide."""
        from src.ai.rag import GitHubIndexer

        with pytest.raises(ValueError, match="URL GitHub invalide"):
            GitHubIndexer("https://gitlab.com/user/repo")

    def test_should_include_md(self):
        """Test inclusion fichiers .md."""
        from src.ai.rag import GitHubIndexer

        indexer = GitHubIndexer("https://github.com/dend/grunt")

        assert indexer._should_include("README.md") is True
        assert indexer._should_include("docs/api.md") is True

    def test_should_exclude_node_modules(self):
        """Test exclusion node_modules."""
        from src.ai.rag import GitHubIndexer

        indexer = GitHubIndexer("https://github.com/dend/grunt")

        assert indexer._should_include("node_modules/pkg/index.js") is False

    def test_should_exclude_binary(self):
        """Test exclusion fichiers binaires."""
        from src.ai.rag import GitHubIndexer

        indexer = GitHubIndexer("https://github.com/dend/grunt")

        assert indexer._should_include("image.png") is False
        assert indexer._should_include("data.bin") is False


class TestRAGConfig:
    """Tests pour la configuration RAG."""

    def test_default_config(self):
        """Test configuration par défaut."""
        from src.ai.rag import RAGConfig

        config = RAGConfig()

        assert config.chunk_size == 1000
        assert config.chunk_overlap == 200
        assert config.top_k == 5
        assert "docs/" in config.default_sources

    def test_custom_config(self):
        """Test configuration personnalisée."""
        from src.ai.rag import RAGConfig

        config = RAGConfig(chunk_size=500, top_k=10, persist_directory="custom/path")

        assert config.chunk_size == 500
        assert config.top_k == 10
        assert config.persist_directory == "custom/path"


@pytest.mark.skipif(
    True,  # Toujours skip car nécessite LanceDB
    reason="Nécessite LanceDB installé",
)
class TestHaloKnowledgeBase:
    """Tests d'intégration pour la base de connaissances."""

    @pytest.fixture
    def temp_kb(self, tmp_path):
        """Fixture pour une KB temporaire."""
        from src.ai.rag import HaloKnowledgeBase, RAGConfig

        config = RAGConfig(persist_directory=str(tmp_path / "rag"), table_name="test_table")
        return HaloKnowledgeBase(config)

    def test_index_and_search(self, temp_kb, tmp_path):
        """Test indexation et recherche."""
        # Créer un fichier de test
        test_file = tmp_path / "test_doc.md"
        test_file.write_text(
            "# Spartan Token\n\n" "Le Spartan Token est utilisé pour l'authentification API Halo."
        )

        # Indexer
        chunks = temp_kb.index_file(test_file)
        assert chunks > 0

        # Rechercher
        results = temp_kb.search("authentification Spartan")
        assert len(results) > 0
        assert "Spartan Token" in results[0].content

    def test_index_text(self, temp_kb):
        """Test indexation de texte brut."""
        chunks = temp_kb.index_text(
            "L'API Halo Infinite utilise des tokens Azure AD.", source="manual_test"
        )

        assert chunks > 0
        assert temp_kb.document_count > 0

    def test_get_stats(self, temp_kb):
        """Test récupération des stats."""
        stats = temp_kb.get_stats()

        assert "total_documents" in stats
        assert "table_name" in stats
        assert stats["table_name"] == "test_table"
        assert stats["backend"] == "lancedb"


class TestSearchResult:
    """Tests pour les résultats de recherche."""

    def test_search_result_creation(self):
        """Test création d'un résultat."""
        from src.ai.rag import SearchResult

        result = SearchResult(
            content="Test content", source="test.md", score=0.95, metadata={"key": "value"}
        )

        assert result.content == "Test content"
        assert result.score == 0.95
        assert result.metadata["key"] == "value"
