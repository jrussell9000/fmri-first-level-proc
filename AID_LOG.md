# AI Development Log

This document discloses the use of AI-assisted development tools in the creation of the **fmri_first_level_proc** analysis pipeline, in accordance with emerging best practices for transparency in scientific software development.

---

## 1. Purpose

This document provides a structured disclosure of AI tool usage during the development of the fmri_first_level_proc pipeline. The disclosure follows the AI Disclosure (AID) Framework (Weaver, 2025) and adheres to recommendations for responsible AI use in scientific computing (Bridgeford et al., 2025; Nussberger et al., 2024; Jamieson et al., 2024). The intent is to ensure that reviewers, collaborators, and end users can assess the nature and extent of AI involvement in the development process.

## 2. Scope

AI assistance was utilized for **analysis pipeline development**, encompassing:

- Code architecture and design
- Statistical methodology review and validation
- Implementation of pipeline modules
- Test suite development and validation
- Documentation drafting and refinement

AI was **not** used for:

- Running analyses on real data
- Interpreting scientific results from pipeline outputs
- Making domain-specific methodological decisions (e.g., selection of covariates, outcome definitions, or study-specific analytical choices)

fmri_first_level_proc is a general-purpose, pip-installable framework for first-level fMRI analyses (task activation, task connectivity, and resting-state connectivity). The pipeline development activities covered above are distinct from its application to any specific dataset or research question.

## 3. Tools Used

Development utilized **Claude Code** (Anthropic), employing two model tiers:

| Model | Tasks |
|-------|-------|
| Claude Opus 4 / Opus 4.6 / Opus 5.5 | Critical review of statistical methods, brainstorming, code quality audits, implementation planning, risk assessment |
| Claude Sonnet 4 / Sonnet 4.6 / Sonnet 5 | Code generation, test design and execution, documentation drafting, literature search and citation checks, independent verification of proposed recommendations, PII and attribution scans, file management |

This dual-tier approach applied the analytical tier to decisions with statistical or methodological consequences, and the implementation tier to well-specified coding tasks under explicit human direction.

## 4. Development Workflow

The pipeline was developed through an iterative, mode-based workflow with the following stages:

1. **Brainstorm** -- Structured discussion of design decisions, trade-offs, and alternative approaches. Every brainstorm session produced a report with explicit decision records (accepted, rejected, deferred).

2. **Critical Review (CR)** -- Formal review of the codebase for statistical correctness, robustness, reproducibility, and defensive coding practices. Each finding was classified by severity (P0/P1/P2) and required explicit human triage (accept, reject, or modify). Reviews also included a manual input-boundary audit of the validation code against the documented input contract; every suspected defect was reproduced by executing a minimal failing case before a fix was planned.

3. **Implement (Plan + Build)** -- Implementation proceeded in two sub-phases: (a) a technical specification mapping each approved change to specific code modifications with risk assessment, and (b) execution of the specification. All plans required human approval before code generation began.

4. **Test** -- Test design and execution after each implementation round, covering unit, integration, edge-case, and statistical invariant tests run against real AFNI binaries on small synthetic data. Each failing test was classified (obsolete test, product defect, or ambiguous) before any edit; product defects were routed back to implementation rather than resolved by changing assertions.

5. **Clean** -- Code quality review for consistency, style, and maintainability.

6. **Document** -- Drafting and updating of user-facing documentation and machine-readable technical specifications, reviewed by the researcher.

Key properties of this workflow:

- All decisions required **explicit human approval** before implementation.
- Every implementation round was followed by a **test round**: the existing regression suite was run before new tests were added and again after; from August 2026 onward, run counts were receipt-verified.
- Every statistical and algorithmic choice was subjected to **formal critical review**, with findings documented and triaged individually.

## 5. Human Oversight

The researcher maintained full oversight and decision authority throughout the development process:

- **(a)** Defined all statistical methodology and analytical approach, including HRF model selection, motion censoring conventions, connectivity computation strategy, and degrees-of-freedom pre-flight logic.

- **(b)** Triaged every critical review finding with explicit accept/reject/modify decisions, documented in brainstorm reports with rationale for each determination.

- **(c)** Approved all implementation plans (technical specifications) before any code generation was executed.

- **(d)** Validated all test results and ensured test coverage aligned with the statistical guarantees required by the pipeline.

- **(e)** Made all domain-specific decisions regarding pipeline architecture, algorithmic choices (e.g., minimum-outlier EPI via AFNI `3dToutcount`, degrees-only rotation convention, `polort -1` with bandpass), and analytical strategy.

- **(f)** Initiated the input-boundary audit after judging the documented input contract insufficiently verified, required execution-based reproduction of each finding, and set the resulting design rules: independent per-block validation with failures recorded in each block's QC summary, the failure status added to the existing QC summary only after confirming compatibility with sibling pipeline consumers, and strict BIDS entity rules limited to discovery mode.

## 6. Audit Trail

A complete record of the structured development process is available in the `.aid/reports/` directory within this repository. The audit trail includes:

- **Brainstorm reports** -- Records of design discussions, decision rationale, and trade-off analyses.
- **Critical review reports** -- Formal findings with severity classifications and human triage decisions.
- **Implementation plans** -- Technical specifications mapping approved changes to code modifications.
- **Implementation build reports** -- Records of executed changes with deviation notes.
- **Test reports** -- Test suite results and coverage summaries.
- **Code quality reviews** -- Clean-pass reports on style and consistency.
- **Documentation reports** -- Records of documentation updates and revisions.

The project-level configuration file used to guide AI interactions is preserved as `.aid/project_claude.md`.

Raw session transcripts are excluded for privacy reasons. The structured reports above capture all substantive technical decisions, rationale, and implementation details.

## 7. References

- Bridgeford, E. W., et al. (2025). Ten simple rules for AI-assisted coding in science. *arXiv preprint*, arXiv:2510.22254.

- Jamieson, A. J., et al. (2024). Protecting scientific integrity in an age of generative AI. *Proceedings of the National Academy of Sciences*, 121(41), e2407886121.

- Nussberger, A.-M., et al. (2024). Ten simple rules for using large language models in science. *PLOS Computational Biology*, 20(7), e1012291.

- Weaver, J. B. (2025). The AI Disclosure (AID) Framework. *arXiv preprint*, arXiv:2408.01904v2.

## Version History

- **v2.4.0** (2026-04-03): Added motion derivative degree configuration, mandatory minimum-outlier EPI generation, and optional pre-regression parcellated time series extraction. AID artifacts synced for all development cycles through v2.4.0.
- **v2.4.0-post1** (2026-04-03): Fixed DOF pre-flight check in rest_conn that overestimated regressor count by 3 (stale polort 2 assumption after v2.3.1 changed to polort -1). Updated module docstring and inline comments. Added run_first_level module-level docstring and corrected its version header. Minor signature formatting in first_level_utils.
- **v2.5.0** (2026-05-01): Added sequenced denoising path for resting-state connectivity (`use_sequenced_bandpass`). Implements interpolate-before-filter ordering (Power et al. 2014; Ciric et al. 2017) using linear NTRP interpolation, with nuisance regressors filtered at the same passband (Hallquist et al. 2013). New utility functions `censor_interpolate_1d_afni` and `bandpass_filter_1d_afni` added to first_level_utils. Config validation, test suite (55 new tests; 515 total passing), and documentation updated.
- **v4.0.0** (2026-11-03): Breaking architectural rewrite. Engine/ledger system (engine.py, checkpoint.py) with stage-hash-based reuse and append-only JSONL ledger. Multi-run identity state machine (runsets.py). Closed config schema with WARNING_CODES and GLOBAL_ONLY_KEYS. Module split: 11 new modules (connectivity.py, engine.py, estimability.py, events.py, inputs.py, names.py, nuisance.py, prep.py, qc.py, roi.py, smoothing.py), 8 rewritten, 1 deleted. Frozen output filenames (names.py), matrix-derived DOF (nuisance.py), trial estimability with pooled energy ratio (estimability.py), data-derived-mask smoothing (smoothing.py), PSC scaling (prep.py), template resampling (roi.py), parcellated (1ddot) and seed-to-voxel (3dTcorr1D) connectivity (connectivity.py), centralized QC schema with cross-producer dedup (qc.py), read-only input checks for --dry-run (inputs.py), BIDS timing file acceptance (events.py). Second round: Power-FD censoring replaces AFNI enorm, 4 new QC keys, Mode A union-of-runs condition check, smoothed-GLM index parity, task_conn nuisance scoping, rest_conn GS derivative and sequenced-backend key-collision fix. Boundary-audit round: manual input-validation audit against the documented contract (9 confirmed bugs, 7 fixed in the audit, 2 routed and fixed in follow-up), null-as-missing exemption for boolean and bandpass keys. Critical review: 15 findings, all independently verified (3-agent PV) and user-decided. Test suite: 751 tests, 0 failures, receipt-verified. Documentation: README.md, INPUT_SPECIFICATION.md, CHANGELOG.md, and AID artifacts updated.
- **v3.1.0** (2026-09-11): Major infrastructure and feature release. Infrastructure: custom exception hierarchy (`FmriFirstLevelError` base with 7 subclasses), 3-stage config pipeline with `ResolvedConfig` dataclass, BIDS derivative output path construction and multi-directory input discovery (`bids.py`), processing DAG with append-only JSONL checkpoint ledger (`checkpoint.py`), AFNI binary preflight and version-lock validation (`runtime.py`), centralized AFNI error wrapping, polort A DOF accounting, `tools.lock.yaml` resilience, and orchestrator harmonization. Features: graded warning accumulator (`get_warnings`/`clear_warnings`), `ToolVersionError` subclass, percent signal change scaling (`scale_to_psc` for all three pipeline types), `stat_buckets` extraction API replacing the legacy `extract`/`extract_stat` fields, `generate_bucket_stats_index` for sub-brick label indexing, and BIDS-format timing file acceptance with legacy CSV deprecation. Documentation: README.md, INPUT_SPECIFICATION.md, and AID artifacts updated.
