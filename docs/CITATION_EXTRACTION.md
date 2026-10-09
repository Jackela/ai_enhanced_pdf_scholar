# PDF citation extraction contract

`CitationService.extract_citations_from_document(document)` keeps its existing input and `list[CitationModel]` result. The API continues to expose `POST /api/citations/extract/{document_id}` with the existing envelope and model fields.

## Supported behavior

The service reads actual PDF bytes through the existing PyMuPDF dependency. A standalone References, Bibliography or 参考文献 heading opens the reference section. Entries must begin with `[n]`, `n.`/`n)` or an author `(year)` pattern. Wrapped lines and subsequent pages are joined until the next entry or a recognized appendix/acknowledgments heading. The resulting `raw_text` retains the source entry, with PDF line breaks normalized to spaces.

Author/year entries can supply authors, year and a conservative first-sentence title. A recognized DOI is preserved. Other fields remain unknown. `confidence_score` is unset because no calibrated accuracy model has been validated. Identical source text in the same document reuses an existing row on sequential extraction; this is not a database concurrency guarantee.

Missing document IDs/paths, missing files, locked PDFs and corrupt PDFs raise `ValueError`, which the existing route maps to HTTP 400. PDFs with no recognized reference section, unsupported entry styles or no embedded text return an empty list and create no citations. Existing manually edited or historical citation rows are not deleted.

## Offline validation

```bash
python -m unittest discover -s validation -v
```

Install the repository dependencies, or the minimal extraction dependencies recorded in `validation/requirements.txt`. This entry bypasses the older pytest fixtures that replace PDF imports with stubs. It generates actual temporary PDF bytes, reads them using PyMuPDF, and stores/reads citations using the production CitationRepository and SQLite connection. It exercises numbered and author/year entries, wrapped/multiple pages, DOI/unknown fields, repeat extraction, absent reference sections, textless input and meaningful failures. Generated PDFs are synthetic test fixtures, not an academic validation corpus. No model calls or network services run in these checks.

## Limits and next work

OCR, two-column reading order, page headers/footers, unusual bibliography titles, arbitrary citation styles and document-to-document identity resolution remain unvalidated. Parsed metadata is a heuristic; source `raw_text` remains the reviewable evidence. A future labeled real-paper corpus should measure precision/recall and metadata accuracy before promoting this experimental extraction to a general capability.

The older `CitationParsingService` offers permissive regex/optional third-party parsing and heuristic confidence values. This repair uses a bounded PDF parser so unsupported entries and unknown fields do not turn into fabricated metadata or calibrated-looking scores. That text-parsing API remains unchanged.
