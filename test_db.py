from pathlib import Path

from src.database import DatabaseMigrator
from src.database.connection import DatabaseConnection

db_path = Path.home() / '.ai_pdf_scholar' / 'documents.db'
print('Testing migrations...')

with DatabaseConnection(str(db_path)) as db:
    print('DB connected')
    migrator = DatabaseMigrator(db)
    print(f'Needs migration: {migrator.needs_migration()}')

print('Done')
