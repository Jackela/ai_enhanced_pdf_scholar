"""Real PDF and SQLite regression checks; no PDF/LLM stubs or network calls."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import pymupdf

from src.database.connection import DatabaseConnection
from src.database.models import CitationModel, DocumentModel
from src.repositories.citation_repository import CitationRepository
from src.services.citation_service import CitationService


class CitationExtractionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = DatabaseConnection(":memory:", enable_monitoring=False)
        self.addCleanup(self.db.close_all_connections)
        self.db.execute("""CREATE TABLE citations (
            id INTEGER PRIMARY KEY, document_id INTEGER, raw_text TEXT,
            authors TEXT, title TEXT, publication_year INTEGER, journal_or_venue TEXT,
            doi TEXT, page_range TEXT, citation_type TEXT, confidence_score REAL,
            created_at TEXT, updated_at TEXT)""")
        self.repo = CitationRepository(self.db)
        self.service = CitationService(self.repo, Mock())

    def pdf(self, pages):
        path = Path(self.tmp.name) / "references.pdf"
        with pymupdf.open() as pdf:
            for text in pages:
                page = pdf.new_page()
                page.insert_text((40, 40), text, fontsize=10)
            pdf.save(path)
        return DocumentModel(
            id=1,
            title="Fixture PDF",
            file_path=str(path),
            file_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
            file_size=path.stat().st_size,
        )

    def test_numbered_references_are_source_text_and_persisted(self):
        doc = self.pdf(
            [
                "Introduction\n[1] This body mention is not a bibliography.\nReferences\n"
                "[1] Ada Lovelace (1843). Notes on the Analytical Engine.\n"
                "[2] Alan Turing (1936). On Computable Numbers.\n"
                "Proceedings of the London Mathematical Society."
            ]
        )
        found = self.service.extract_citations_from_document(doc)
        self.assertEqual(len(found), 2)
        self.assertIn("Ada Lovelace", found[0].raw_text)
        self.assertNotIn("Sample", found[0].raw_text)
        self.assertEqual(found[0].publication_year, 1843)
        self.assertEqual(found[1].title, "On Computable Numbers")
        self.assertIn("Proceedings", found[1].raw_text)
        self.assertEqual(len(self.repo.find_by_document_id(1)), 2)
        self.assertEqual(found[0].to_api_dict()["document_id"], 1)

    def test_repeated_extraction_does_not_duplicate_rows(self):
        doc = self.pdf(
            ["References\n[1] Ada Lovelace (1843). Notes on the Analytical Engine."]
        )
        first = self.service.extract_citations_from_document(doc)
        second = self.service.extract_citations_from_document(doc)
        self.assertEqual([c.id for c in first], [c.id for c in second])
        self.assertEqual(len(self.repo.find_by_document_id(1)), 1)

    def test_apa_references_and_page_continuation(self):
        doc = self.pdf(
            [
                "Bibliography\nLovelace, A. (1843). Notes on the Analytical Engine.",
                "Turing, A. (1936). On Computable Numbers.\nWith an Application to the Entscheidungsproblem.",
            ]
        )
        found = self.service.extract_citations_from_document(doc)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0].authors, "Lovelace, A.")
        self.assertIn("Entscheidungsproblem", found[1].raw_text)

    def test_doi_and_unknown_metadata_preserved_without_invention(self):
        doc = self.pdf(
            ["References\n1. An unstructured reference, DOI: 10.1234/example."]
        )
        found = self.service.extract_citations_from_document(doc)
        self.assertEqual(found[0].doi, "10.1234/example")
        self.assertIsNone(found[0].authors)
        self.assertIsNone(found[0].title)

    def test_missing_section_returns_empty_without_writing(self):
        doc = self.pdf(["Introduction\n[1] This is only an in-text citation, 2021."])
        self.assertEqual(self.service.extract_citations_from_document(doc), [])
        self.assertEqual(self.repo.find_by_document_id(1), [])

    def test_textless_pdf_returns_empty(self):
        self.assertEqual(
            self.service.extract_citations_from_document(self.pdf([""])), []
        )

    def test_appendix_is_not_added_to_reference(self):
        doc = self.pdf(
            [
                "References\n[1] Lovelace, A. (1843). Notes.\nAppendix A\nUnrelated appendix content"
            ]
        )
        found = self.service.extract_citations_from_document(doc)
        self.assertNotIn("Unrelated", found[0].raw_text)

    def test_missing_file_and_invalid_document_fail_without_writes(self):
        doc = self.pdf(["References\n[1] Lovelace, A. (1843). Notes."])
        Path(doc.file_path).unlink()
        with self.assertRaises(ValueError):
            self.service.extract_citations_from_document(doc)
        with self.assertRaises(ValueError):
            self.service.extract_citations_from_document(None)
        self.assertEqual(self.repo.find_by_document_id(1), [])

    def test_corrupt_pdf_fails_without_writes(self):
        doc = self.pdf(["References"])
        Path(doc.file_path).write_bytes(b"not a PDF")
        with self.assertRaises(ValueError):
            self.service.extract_citations_from_document(doc)
        self.assertEqual(self.repo.find_by_document_id(1), [])


if __name__ == "__main__":
    unittest.main()
