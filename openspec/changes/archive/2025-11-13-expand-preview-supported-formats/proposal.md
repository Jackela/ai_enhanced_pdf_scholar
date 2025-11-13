## Why
- Previews currently work only for PDFs; many users upload DOCX, PPTX, or image formats, forcing them to download files just to inspect them.
- External converters (LibreOffice, ImageMagick) or service-based pipelines may be needed, and we must decide the scope and resource impact before implementation.
- Without a plan, support requests for non-PDF previews will accumulate and engineers might ship ad-hoc conversions without safety limits.

## What Changes
- Research and document the minimal path to support at least DOCX and image files (e.g., using LibreOffice headless conversion + existing rasterization pipeline).
- Define configuration flags (enable/disable converters, max file size, timeout) and storage strategy for converted artifacts.
- Extend specs to describe behaviour for each supported type, failure codes, and observability requirements.
- Outline rollout plan (initial optional feature flag, canary environment tests) and risk mitigations.

## Impact
- Unlock previews for a much larger portion of the library.
- Provide a vetted architectural plan so future implementation can proceed confidently.
- Sets expectations for resource usage and operational controls.
