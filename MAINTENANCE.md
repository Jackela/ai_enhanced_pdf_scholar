# Maintenance and evidence

Markdown files are the editable documentation source. Read the relevant source, current branch and existing changes before modifying behavior. Record the source revision, actual commands, exit codes and unresolved work in Markdown and JSON. This repair restores the intended citation extraction behavior without changing the API signature or schema.

## Verification entry

```bash
python -m pip install -r validation/requirements.txt
python -m unittest discover -s validation -v
```

The dedicated GitHub `PDF citation extraction` workflow runs the same offline suite without existing PDF stubs or external model calls. `maintenance-evidence.json` records the baseline and candidate scope. See [the extraction contract](docs/CITATION_EXTRACTION.md) for supported layouts and limitations.

## Evidence authority

The historical `CURRENT_VERIFICATION_STATUS.md` describes a 2025 Windows environment failure. Its completion language and old CI success are not evidence of current deployment, provider access, OCR, extraction accuracy or product acceptance. Some legacy CI steps remain advisory or mask failures; their successful workflow status is not a claim that every check passed. This repair introduces a blocking extraction check without lowering existing thresholds.

The old RAG wrapper has a fixed test mode; the API uses EnhancedRAGService and chooses test mode from provider-key availability. Neither path was live-provider validated in this repair. Citation recommendations still contain incomplete similarity logic, and existing sample rows are not automatically cleaned up; review them separately before using old stored networks as research evidence.
