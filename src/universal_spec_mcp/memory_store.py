"""Memory store for persistent architectural decisions and context using SQLite with FTS5."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MemoryStore:
    """
    Manages persistent architectural decisions and context using SQLite.
    Uses FTS5 (Full-Text Search) extension for efficient text search.
    """
    
    def __init__(self, db_path: Path | str = ".specs/.system/memory.db"):
        """
        Initialize the memory store.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._ensure_db_exists()
    
    def _ensure_db_exists(self) -> None:
        """Ensure the database file and its parent directory exist, and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Create the main memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Create FTS5 virtual table for full-text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    feature_name,
                    content,
                    memory_type,
                    content='memories',
                    content_rowid='id'
                )
            """)
            
            # Create triggers to keep FTS5 table in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, feature_name, content, memory_type)
                    VALUES (new.id, new.feature_name, new.content, new.memory_type);
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    DELETE FROM memories_fts WHERE rowid = old.id;
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    DELETE FROM memories_fts WHERE rowid = old.id;
                    INSERT INTO memories_fts(rowid, feature_name, content, memory_type)
                    VALUES (new.id, new.feature_name, new.content, new.memory_type);
                END
            """)
            
            conn.commit()
            conn.close()
    
    def add_memory(
        self,
        feature_name: str,
        content: str,
        memory_type: str = "decision",
        metadata: dict[str, Any] | None = None
    ) -> int:
        """
        Add a new memory to the store.
        
        Args:
            feature_name: Name of the feature this memory relates to
            content: The memory content (e.g., architectural decision, context)
            memory_type: Type of memory (e.g., "decision", "context", "constraint")
            metadata: Optional additional metadata as a dictionary
            
        Returns:
            The ID of the created memory
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            created_at = datetime.now(timezone.utc).isoformat()
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute("""
                INSERT INTO memories (feature_name, content, memory_type, created_at, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (feature_name, content, memory_type, created_at, metadata_json))
            
            memory_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # lastrowid should always be an int after INSERT, but type checker needs assurance
            return memory_id if memory_id is not None else 0
    
    def search_memory(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search memories using full-text search.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of matching memory dictionaries, ordered by relevance
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Use FTS5 MATCH for full-text search
            cursor.execute("""
                SELECT m.id, m.feature_name, m.content, m.memory_type, m.created_at, m.metadata
                FROM memories m
                JOIN memories_fts fts ON m.id = fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            results = []
            for row in cursor.fetchall():
                memory = {
                    'id': row['id'],
                    'feature_name': row['feature_name'],
                    'content': row['content'],
                    'memory_type': row['memory_type'],
                    'created_at': row['created_at'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else None
                }
                results.append(memory)
            
            conn.close()
            return results
    
    def get_memories_by_feature(self, feature_name: str) -> list[dict[str, Any]]:
        """
        Get all memories for a specific feature.
        
        Args:
            feature_name: Name of the feature
            
        Returns:
            List of memory dictionaries for the feature
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, feature_name, content, memory_type, created_at, metadata
                FROM memories
                WHERE feature_name = ?
                ORDER BY created_at DESC
            """, (feature_name,))
            
            results = []
            for row in cursor.fetchall():
                memory = {
                    'id': row['id'],
                    'feature_name': row['feature_name'],
                    'content': row['content'],
                    'memory_type': row['memory_type'],
                    'created_at': row['created_at'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else None
                }
                results.append(memory)
            
            conn.close()
            return results
    
    def get_memory(self, memory_id: int) -> dict[str, Any] | None:
        """
        Get a specific memory by ID.
        
        Args:
            memory_id: The ID of the memory to retrieve
            
        Returns:
            The memory dictionary if found, None otherwise
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, feature_name, content, memory_type, created_at, metadata
                FROM memories
                WHERE id = ?
            """, (memory_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row['id'],
                    'feature_name': row['feature_name'],
                    'content': row['content'],
                    'memory_type': row['memory_type'],
                    'created_at': row['created_at'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else None
                }
            
            return None
    
    def delete_memory(self, memory_id: int) -> bool:
        """
        Delete a memory by ID.
        
        Args:
            memory_id: The ID of the memory to delete
            
        Returns:
            True if the memory was deleted, False if not found
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            
            return deleted
    
    def list_all_memories(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        List all memories, most recent first.
        
        Args:
            limit: Maximum number of memories to return
            
        Returns:
            List of memory dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, feature_name, content, memory_type, created_at, metadata
                FROM memories
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                memory = {
                    'id': row['id'],
                    'feature_name': row['feature_name'],
                    'content': row['content'],
                    'memory_type': row['memory_type'],
                    'created_at': row['created_at'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else None
                }
                results.append(memory)
            
            conn.close()
            return results

# Made with Bob
