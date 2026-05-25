"""Directive store for managing project-wide rules and guidelines."""

import json
import threading
from pathlib import Path
from typing import Any


class DirectiveStore:
    """
    Manages persistent, project-wide directives (rules) stored in a JSON file.
    Thread-safe for concurrent access.
    """
    
    def __init__(self, directives_path: Path | str = ".specs/.system/directives.json"):
        """
        Initialize the directive store.
        
        Args:
            directives_path: Path to the directives JSON file
        """
        self.directives_path = Path(directives_path)
        self._lock = threading.Lock()
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """Ensure the directives file and its parent directory exist."""
        self.directives_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.directives_path.exists():
            self.directives_path.write_text(json.dumps([], indent=2))
    
    def _read_directives(self) -> list[dict[str, Any]]:
        """
        Read directives from the JSON file.
        
        Returns:
            List of directive dictionaries
        """
        try:
            with open(self.directives_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _write_directives(self, directives: list[dict[str, Any]]) -> None:
        """
        Write directives to the JSON file.
        
        Args:
            directives: List of directive dictionaries to write
        """
        with open(self.directives_path, 'w', encoding='utf-8') as f:
            json.dump(directives, f, indent=2, ensure_ascii=False)
    
    def add_directive(self, directive: str, category: str = "general") -> dict[str, Any]:
        """
        Add a new directive to the store.
        
        Args:
            directive: The directive text
            category: Category for organizing directives (e.g., "architecture", "testing")
            
        Returns:
            The created directive dictionary with id, text, and category
        """
        with self._lock:
            directives = self._read_directives()
            
            # Generate a simple numeric ID
            next_id = max([d.get('id', 0) for d in directives], default=0) + 1
            
            new_directive = {
                'id': next_id,
                'text': directive,
                'category': category
            }
            
            directives.append(new_directive)
            self._write_directives(directives)
            
            return new_directive
    
    def remove_directive(self, directive_id: int) -> bool:
        """
        Remove a directive by its ID.
        
        Args:
            directive_id: The ID of the directive to remove
            
        Returns:
            True if the directive was removed, False if not found
        """
        with self._lock:
            directives = self._read_directives()
            original_count = len(directives)
            
            directives = [d for d in directives if d.get('id') != directive_id]
            
            if len(directives) < original_count:
                self._write_directives(directives)
                return True
            
            return False
    
    def list_directives(self) -> list[dict[str, Any]]:
        """
        List all directives.
        
        Returns:
            List of all directive dictionaries
        """
        with self._lock:
            return self._read_directives()
    
    def get_directive(self, directive_id: int) -> dict[str, Any] | None:
        """
        Get a specific directive by ID.
        
        Args:
            directive_id: The ID of the directive to retrieve
            
        Returns:
            The directive dictionary if found, None otherwise
        """
        with self._lock:
            directives = self._read_directives()
            for directive in directives:
                if directive.get('id') == directive_id:
                    return directive
            return None
    
    def get_directives_by_category(self, category: str) -> list[dict[str, Any]]:
        """
        Get all directives in a specific category.
        
        Args:
            category: The category to filter by
            
        Returns:
            List of directive dictionaries in the specified category
        """
        with self._lock:
            directives = self._read_directives()
            return [d for d in directives if d.get('category') == category]
    
    def format_for_context(self, category: str | None = None) -> str:
        """
        Format directives as a string for injection into tool responses.
        
        Args:
            category: Optional category to filter by. If None, returns all directives.
        
        Returns:
            Formatted string of directives (filtered by category if specified)
        """
        if category:
            directives = self.get_directives_by_category(category)
        else:
            directives = self.list_directives()
        
        if not directives:
            return ""
        
        lines = ["\n## Project Directives"]
        if category:
            lines.append(f"The following {category} rules must be followed:\n")
        else:
            lines.append("The following project-wide rules must be followed:\n")
        
        # Group by category
        categories: dict[str, list[dict[str, Any]]] = {}
        for directive in directives:
            cat = directive.get('category', 'general')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(directive)
        
        for cat, cat_directives in sorted(categories.items()):
            lines.append(f"### {cat.title()}")
            for directive in cat_directives:
                lines.append(f"- {directive['text']}")
            lines.append("")
        
        return "\n".join(lines)

# Made with Bob
