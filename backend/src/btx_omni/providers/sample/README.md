# Authoritative SAMPLE runtime boundary

This directory is the single authoritative runtime boundary for SAMPLE fixture
composition. `build_sample_environment()` builds the base environment, and
SAMPLE runtime construction composes it with `enhance_environment()` before
consumers are initialized. Files under `docs/research/` are research or
import inputs only; they are not runtime fixture storage.

The explicit commercial import helper is operator/import-only and is never
called by SAMPLE application startup.
