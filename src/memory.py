"""Vector Memory Store - The FDE's episodic memory for continual learning.

Uses ChromaDB to store column-name -> canonical-field mappings as embeddings.
When the agent encounters a new column, it queries this store for similar
previously-learned mappings before asking the human.
"""

import os
import chromadb
from rich.console import Console

from src.config import Config

console = Console()


class MemoryStore:
    """Persistent vector memory for learned data mappings."""

    def __init__(self):
        os.makedirs(Config.MEMORY_DIR, exist_ok=True)
        self._client = chromadb.PersistentClient(path=Config.MEMORY_DIR)
        try:
            self._collection = self._client.get_or_create_collection(
                name="column_mappings",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            # Stale collection on disk — wipe and recreate
            try:
                self._client.delete_collection("column_mappings")
            except Exception:
                pass
            self._collection = self._client.create_collection(
                name="column_mappings",
                metadata={"hnsw:space": "cosine"},
            )

    def store_mapping(self, source_column: str, target_field: str, client_name: str) -> None:
        """Store a learned mapping: source column name -> target schema field."""
        doc_id = f"{client_name}_{source_column}"
        self._collection.upsert(
            ids=[doc_id],
            documents=[source_column],
            metadatas=[{
                "source_column": source_column,
                "target_field": target_field,
                "client_name": client_name,
            }],
        )
        console.print(
            f"  [green]Memory stored:[/green] '{source_column}' -> '{target_field}' "
            f"(from {client_name})"
        )

    def lookup(self, column_name: str, n_results: int = 3) -> list[dict]:
        """Look up similar column names in memory.

        Returns a list of matches with distance scores.
        Lower distance = better match (cosine distance).
        """
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[column_name],
            n_results=min(n_results, self._collection.count()),
        )

        matches = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            metadata = results["metadatas"][0][i]
            matches.append({
                "source_column": metadata["source_column"],
                "target_field": metadata["target_field"],
                "client_name": metadata["client_name"],
                "distance": distance,
                "is_confident": distance <= Config.MEMORY_DISTANCE_THRESHOLD,
            })

        return matches

    def find_match(self, column_name: str) -> dict | None:
        """Find the best memory match for a column name.

        Returns the match if it's within the confidence threshold, else None.
        """
        matches = self.lookup(column_name, n_results=1)
        if matches and matches[0]["is_confident"]:
            return matches[0]
        return None

    def get_all_mappings(self) -> list[dict]:
        """Return all stored mappings."""
        if self._collection.count() == 0:
            return []
        all_data = self._collection.get(include=["metadatas", "documents"])
        mappings = []
        for i in range(len(all_data["ids"])):
            mappings.append({
                "source_column": all_data["metadatas"][i]["source_column"],
                "target_field": all_data["metadatas"][i]["target_field"],
                "client_name": all_data["metadatas"][i]["client_name"],
            })
        return mappings

    def clear(self) -> None:
        """Clear all stored mappings (for demo reset)."""
        # Remove all documents instead of deleting/recreating the collection
        # to avoid stale UUID references in ChromaDB's PersistentClient.
        if self._collection.count() > 0:
            all_ids = self._collection.get()["ids"]
            if all_ids:
                self._collection.delete(ids=all_ids)
        console.print("  [yellow]Memory cleared.[/yellow]")

    @property
    def count(self) -> int:
        return self._collection.count()
