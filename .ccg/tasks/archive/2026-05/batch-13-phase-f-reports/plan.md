# Implementation Plan

1. Add regression tests for download safety, streaming responses, report generation, manifest integrity, and the scheduler job.
2. Implement manifest helpers and report generation helpers for markdown, PDF, PNG, and bundle artifacts.
3. Replace report download route stubs with authenticated streaming responses and update the report services layer.
4. Wire the featured digest scheduler into app lifespan and add the CLI entry point for manual digest generation.
5. Add the new Python dependencies and verify the backend test suite.
