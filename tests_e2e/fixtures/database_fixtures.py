"""
Database Fixtures for E2E Testing

Provides database setup, seeding, and cleanup utilities for testing.
"""

import pytest
import sqlite3
from pathlib import Path
from typing import Generator, Dict, Any, List
import json
from datetime import datetime, timedelta
import random
import shutil


class DatabaseManager:
    """
    Manage database operations for testing.
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.connection = None
        
    def connect(self):
        """Connect to the database."""
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.row_factory = sqlite3.Row
        return self.connection
    
    def disconnect(self):
        """Disconnect from the database."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def execute(self, query: str, params: tuple = None) -> sqlite3.Cursor:
        """Execute a query."""
        if not self.connection:
            self.connect()
        return self.connection.execute(query, params or ())
    
    def executemany(self, query: str, params: List[tuple]) -> sqlite3.Cursor:
        """Execute multiple queries."""
        if not self.connection:
            self.connect()
        return self.connection.executemany(query, params)
    
    def commit(self):
        """Commit the current transaction."""
        if self.connection:
            self.connection.commit()
    
    def rollback(self):
        """Rollback the current transaction."""
        if self.connection:
            self.connection.rollback()
    
    def create_tables(self):
        """Create database tables for testing."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT,
                file_size INTEGER,
                page_count INTEGER,
                content_hash TEXT,
                status TEXT DEFAULT 'pending',
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_date TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS citations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                citation_text TEXT,
                authors TEXT,
                year INTEGER,
                title TEXT,
                source TEXT,
                page_number INTEGER,
                confidence_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS rag_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query_text TEXT NOT NULL,
                response_text TEXT,
                document_ids TEXT,
                confidence_score REAL,
                processing_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                old_value TEXT,
                new_value TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_citations_document_id ON citations(document_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
            """
        ]
        
        for query in queries:
            self.execute(query)
        self.commit()
    
    def drop_all_tables(self):
        """Drop all tables."""
        tables = [
            'audit_logs', 'sessions', 'rag_queries',
            'citations', 'documents', 'users'
        ]
        
        for table in tables:
            self.execute(f"DROP TABLE IF EXISTS {table}")
        self.commit()
    
    def clear_all_data(self):
        """Clear all data from tables without dropping them."""
        tables = [
            'audit_logs', 'sessions', 'rag_queries',
            'citations', 'documents', 'users'
        ]
        
        for table in tables:
            self.execute(f"DELETE FROM {table}")
        self.commit()
    
    def seed_users(self, count: int = 10) -> List[int]:
        """Seed the database with test users."""
        user_ids = []
        
        for i in range(count):
            role = 'admin' if i == 0 else 'user' if i < 8 else 'guest'
            cursor = self.execute(
                """
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (
                    f"user_{i}",
                    f"user{i}@example.com",
                    f"hashed_password_{i}",  # In real tests, use proper hashing
                    role
                )
            )
            user_ids.append(cursor.lastrowid)
        
        self.commit()
        return user_ids
    
    def seed_documents(self, user_ids: List[int], count: int = 50) -> List[int]:
        """Seed the database with test documents."""
        document_ids = []
        statuses = ['pending', 'processing', 'completed', 'failed']
        
        for i in range(count):
            user_id = random.choice(user_ids)
            status = random.choice(statuses)
            
            cursor = self.execute(
                """
                INSERT INTO documents (
                    user_id, title, filename, file_path,
                    file_size, page_count, status,
                    processed_date, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    f"Document {i}",
                    f"document_{i}.pdf",
                    f"/storage/documents/document_{i}.pdf",
                    random.randint(100000, 10000000),
                    random.randint(1, 500),
                    status,
                    datetime.now() - timedelta(hours=random.randint(0, 72))
                    if status == 'completed' else None,
                    json.dumps({
                        "author": f"Author {i % 10}",
                        "category": ["Research", "Tutorial", "Reference"][i % 3],
                        "tags": [f"tag{j}" for j in range(random.randint(1, 5))]
                    })
                )
            )
            document_ids.append(cursor.lastrowid)
        
        self.commit()
        return document_ids
    
    def seed_citations(self, document_ids: List[int]) -> List[int]:
        """Seed the database with test citations."""
        citation_ids = []
        
        for doc_id in random.sample(document_ids, min(30, len(document_ids))):
            citation_count = random.randint(1, 10)
            
            for i in range(citation_count):
                cursor = self.execute(
                    """
                    INSERT INTO citations (
                        document_id, citation_text, authors,
                        year, title, source, page_number,
                        confidence_score
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        f"[{i+1}] Citation text for reference",
                        f"Author{i}, Co-Author{i}",
                        2020 + random.randint(0, 4),
                        f"Research Paper Title {i}",
                        ["Journal", "Conference", "Book"][random.randint(0, 2)],
                        random.randint(1, 300),
                        random.uniform(0.7, 1.0)
                    )
                )
                citation_ids.append(cursor.lastrowid)
        
        self.commit()
        return citation_ids
    
    def seed_rag_queries(self, user_ids: List[int], document_ids: List[int]) -> List[int]:
        """Seed the database with test RAG queries."""
        query_ids = []
        sample_queries = [
            "What is machine learning?",
            "Explain neural networks",
            "How does deep learning work?",
            "What are transformers in NLP?",
            "Describe reinforcement learning",
            "What is computer vision?",
            "Explain gradient descent",
            "What are GANs?",
            "How do LLMs work?",
            "What is transfer learning?"
        ]
        
        for _ in range(30):
            user_id = random.choice(user_ids)
            query_text = random.choice(sample_queries)
            selected_docs = random.sample(
                document_ids,
                min(random.randint(1, 5), len(document_ids))
            )
            
            cursor = self.execute(
                """
                INSERT INTO rag_queries (
                    user_id, query_text, response_text,
                    document_ids, confidence_score,
                    processing_time
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    query_text,
                    f"Response to: {query_text}. This is a detailed answer...",
                    json.dumps(selected_docs),
                    random.uniform(0.5, 1.0),
                    random.uniform(0.5, 5.0)
                )
            )
            query_ids.append(cursor.lastrowid)
        
        self.commit()
        return query_ids
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        
        tables = ['users', 'documents', 'citations', 'rag_queries', 'sessions', 'audit_logs']
        
        for table in tables:
            cursor = self.execute(f"SELECT COUNT(*) as count FROM {table}")
            stats[f"{table}_count"] = cursor.fetchone()['count']
        
        # Get document status distribution
        cursor = self.execute(
            "SELECT status, COUNT(*) as count FROM documents GROUP BY status"
        )
        stats['document_status'] = {
            row['status']: row['count'] for row in cursor.fetchall()
        }
        
        # Get user role distribution
        cursor = self.execute(
            "SELECT role, COUNT(*) as count FROM users GROUP BY role"
        )
        stats['user_roles'] = {
            row['role']: row['count'] for row in cursor.fetchall()
        }
        
        return stats


@pytest.fixture
def test_database() -> Generator[DatabaseManager, None, None]:
    """
    Provide a clean test database.
    """
    # Create test database
    db_path = Path("tests_e2e/test_data/test_database.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
    
    # Create and setup database
    db_manager = DatabaseManager(db_path)
    db_manager.create_tables()
    
    yield db_manager
    
    # Cleanup
    db_manager.disconnect()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def seeded_database(test_database: DatabaseManager) -> DatabaseManager:
    """
    Provide a database with seeded test data.
    """
    # Seed data
    user_ids = test_database.seed_users(10)
    document_ids = test_database.seed_documents(user_ids, 50)
    test_database.seed_citations(document_ids)
    test_database.seed_rag_queries(user_ids, document_ids)
    
    return test_database


@pytest.fixture
def database_backup() -> Generator[callable, None, None]:
    """
    Provide a function to backup and restore the database.
    """
    backup_dir = Path("tests_e2e/test_data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    def backup_restore(action: str, db_path: Path = None, backup_name: str = "backup"):
        backup_path = backup_dir / f"{backup_name}.db"
        
        if action == "backup" and db_path:
            if db_path.exists():
                shutil.copy2(db_path, backup_path)
                return backup_path
        
        elif action == "restore" and db_path:
            if backup_path.exists():
                shutil.copy2(backup_path, db_path)
                return db_path
        
        elif action == "list":
            return list(backup_dir.glob("*.db"))
        
        return None
    
    yield backup_restore
    
    # Cleanup backups
    for backup in backup_dir.glob("*.db"):
        backup.unlink()


@pytest.fixture
def database_monitor(test_database: DatabaseManager) -> Generator[callable, None, None]:
    """
    Provide a function to monitor database changes during tests.
    """
    initial_stats = test_database.get_statistics()
    
    def get_changes():
        current_stats = test_database.get_statistics()
        changes = {}
        
        for key, initial_value in initial_stats.items():
            current_value = current_stats.get(key)
            if isinstance(initial_value, dict) and isinstance(current_value, dict):
                # Compare dictionaries
                dict_changes = {}
                for sub_key in set(initial_value.keys()) | set(current_value.keys()):
                    initial_sub = initial_value.get(sub_key, 0)
                    current_sub = current_value.get(sub_key, 0)
                    if initial_sub != current_sub:
                        dict_changes[sub_key] = {
                            'before': initial_sub,
                            'after': current_sub,
                            'change': current_sub - initial_sub
                        }
                if dict_changes:
                    changes[key] = dict_changes
            elif initial_value != current_value:
                changes[key] = {
                    'before': initial_value,
                    'after': current_value,
                    'change': current_value - initial_value
                }
        
        return changes
    
    yield get_changes