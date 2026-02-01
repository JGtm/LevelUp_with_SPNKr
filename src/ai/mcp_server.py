#!/usr/bin/env python3
"""
Serveur MCP pour le RAG Halo.

Ce serveur expose les fonctionnalités de recherche RAG via le protocole MCP
pour intégration dans Cursor et autres outils compatibles.

Usage:
    # Lancer le serveur
    python -m src.ai.mcp_server

    # Configuration dans .cursor/mcp.json:
    {
      "mcpServers": {
        "halo-rag": {
          "command": "python",
          "args": ["-m", "src.ai.mcp_server"],
          "disabled": false
        }
      }
    }

Outils exposés:
    - search_knowledge: Recherche sémantique dans la base
    - get_api_doc: Récupère la documentation d'un endpoint API
    - get_context: Génère un contexte pour un prompt LLM
    - index_file: Indexe un fichier local
    - get_stats: Statistiques de la base
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))


class MCPServer:
    """Serveur MCP simple pour le RAG."""

    def __init__(self):
        self.kb = None
        self._initialized = False

    def _ensure_initialized(self):
        """Initialise la base de connaissances si nécessaire."""
        if self._initialized:
            return

        try:
            from src.ai.rag import HaloKnowledgeBase, RAGConfig

            config = RAGConfig(persist_directory="data/rag")
            self.kb = HaloKnowledgeBase(config)
            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"LanceDB non installé: {e}") from e

    def get_tools(self) -> list[dict[str, Any]]:
        """Retourne la liste des outils disponibles."""
        return [
            {
                "name": "search_knowledge",
                "description": "Recherche sémantique dans la base de connaissances Halo. "
                "Utiliser pour trouver de la documentation sur l'API, "
                "des exemples de code, ou des patterns du projet.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Question ou termes de recherche",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Nombre de résultats (défaut: 5)",
                            "default": 5,
                        },
                        "source_filter": {
                            "type": "string",
                            "description": "Filtrer par type de source: 'github', 'file', 'text'",
                            "enum": ["github", "file", "text"],
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_api_doc",
                "description": "Recherche la documentation d'un endpoint ou concept de l'API Halo. "
                "Optimisé pour trouver des infos sur SPNKr, Grunt, authentification, etc.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Sujet à rechercher (ex: 'Spartan Token', 'match stats', 'career rank')",
                        }
                    },
                    "required": ["topic"],
                },
            },
            {
                "name": "get_context",
                "description": "Génère un contexte formaté pour un prompt LLM basé sur une question. "
                "Retourne les chunks les plus pertinents avec leurs sources.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Question pour laquelle générer le contexte",
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Limite approximative de tokens (défaut: 4000)",
                            "default": 4000,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "index_file",
                "description": "Indexe un fichier local dans la base de connaissances.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Chemin vers le fichier à indexer",
                        }
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "get_stats",
                "description": "Retourne les statistiques de la base de connaissances.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Exécute un outil et retourne le résultat."""
        self._ensure_initialized()

        if name == "search_knowledge":
            return self._search_knowledge(
                query=arguments["query"],
                top_k=arguments.get("top_k", 5),
                source_filter=arguments.get("source_filter"),
            )

        elif name == "get_api_doc":
            return self._get_api_doc(topic=arguments["topic"])

        elif name == "get_context":
            return self._get_context(
                query=arguments["query"], max_tokens=arguments.get("max_tokens", 4000)
            )

        elif name == "index_file":
            return self._index_file(file_path=arguments["file_path"])

        elif name == "get_stats":
            return self._get_stats()

        else:
            raise ValueError(f"Outil inconnu: {name}")

    def _search_knowledge(
        self, query: str, top_k: int = 5, source_filter: str | None = None
    ) -> dict[str, Any]:
        """Recherche dans la base de connaissances."""
        if source_filter:
            results = self.kb.search_by_source(query, source_filter, top_k)
        else:
            results = self.kb.search(query, top_k)

        return {
            "query": query,
            "results": [
                {
                    "content": r.content,
                    "source": r.source,
                    "score": round(r.score, 3),
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "total": len(results),
        }

    def _get_api_doc(self, topic: str) -> dict[str, Any]:
        """Recherche de documentation API."""
        # Enrichir la requête pour cibler la doc API
        enhanced_query = f"API Halo Infinite {topic} endpoint documentation"

        results = self.kb.search(enhanced_query, top_k=3)

        # Formater pour une lecture facile
        formatted_docs = []
        for r in results:
            formatted_docs.append(
                {
                    "content": r.content,
                    "source": r.source,
                    "relevance": "high" if r.score > 0.8 else "medium" if r.score > 0.6 else "low",
                }
            )

        return {
            "topic": topic,
            "documentation": formatted_docs,
            "note": "Documentation extraite de Grunt, SPNKr et fichiers locaux",
        }

    def _get_context(self, query: str, max_tokens: int = 4000) -> dict[str, Any]:
        """Génère un contexte pour prompt LLM."""
        context = self.kb.get_context_for_prompt(query, max_tokens)

        return {
            "query": query,
            "context": context,
            "estimated_tokens": len(context) // 4,
            "usage": "Injectez ce contexte dans votre prompt système ou utilisateur",
        }

    def _index_file(self, file_path: str) -> dict[str, Any]:
        """Indexe un fichier."""
        path = Path(file_path)

        if not path.exists():
            return {"error": f"Fichier non trouvé: {file_path}"}

        chunks = self.kb.index_file(path)

        return {"file": file_path, "chunks_indexed": chunks, "status": "success"}

    def _get_stats(self) -> dict[str, Any]:
        """Retourne les stats."""
        return self.kb.get_stats()


def run_stdio_server():
    """Lance le serveur MCP en mode stdio (JSON-RPC)."""
    server = MCPServer()

    # Écrire les capabilities
    capabilities = {
        "jsonrpc": "2.0",
        "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "halo-rag", "version": "1.0.0"},
            "capabilities": {"tools": {}},
        },
    }

    def send_response(response: dict):
        """Envoie une réponse JSON-RPC."""
        msg = json.dumps(response)
        sys.stdout.write(f"Content-Length: {len(msg)}\r\n\r\n{msg}")
        sys.stdout.flush()

    def read_request() -> dict | None:
        """Lit une requête JSON-RPC."""
        # Lire les headers
        headers = {}
        while True:
            line = sys.stdin.readline()
            if line == "\r\n" or line == "\n":
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        # Lire le contenu
        content_length = int(headers.get("content-length", 0))
        if content_length == 0:
            return None

        content = sys.stdin.read(content_length)
        return json.loads(content)

    # Boucle principale
    while True:
        try:
            request = read_request()
            if request is None:
                break

            method = request.get("method", "")
            request_id = request.get("id")
            params = request.get("params", {})

            if method == "initialize":
                send_response(
                    {"jsonrpc": "2.0", "id": request_id, "result": capabilities["result"]}
                )

            elif method == "tools/list":
                send_response(
                    {"jsonrpc": "2.0", "id": request_id, "result": {"tools": server.get_tools()}}
                )

            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})

                try:
                    result = server.call_tool(tool_name, arguments)
                    send_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(result, indent=2, ensure_ascii=False),
                                    }
                                ]
                            },
                        }
                    )
                except Exception as e:
                    send_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {"code": -32603, "message": str(e)},
                        }
                    )

            else:
                # Méthode non supportée
                send_response(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }
                )

        except Exception as e:
            # Erreur fatale
            sys.stderr.write(f"Error: {e}\n")
            break


if __name__ == "__main__":
    run_stdio_server()
