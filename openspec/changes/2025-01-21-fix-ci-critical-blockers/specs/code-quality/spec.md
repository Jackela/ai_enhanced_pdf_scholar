# Code Quality Specification

## ADDED Requirements

### Requirement: Code Formatting Standards
All Python code SHALL adhere to Black code formatting standards with zero violations.

The codebase MUST pass Black's formatting checks in CI. Any formatting violations will cause the CI build to fail.

#### Scenario: Black formatting check passes
- **GIVEN** Python code exists in src/ and backend/ directories
- **WHEN** `black --check src backend` is executed
- **THEN** zero files are reported as needing reformatting
- **AND** the command exits with status code 0

#### Scenario: Automated formatting application
- **GIVEN** code formatting violations exist
- **WHEN** `black src backend` is executed
- **THEN** all Python files are automatically formatted to Black standards
- **AND** subsequent formatting checks pass

#### Scenario: Long line handling
- **GIVEN** code has lines longer than 88 characters (Black's default)
- **WHEN** Black formatter is applied
- **THEN** long lines are intelligently wrapped
- **AND** function calls, string literals, and expressions are formatted appropriately
- **AND** line length violations are resolved

### Requirement: Frontend Linting Standards
The frontend codebase SHALL have zero ESLint warnings when using the configured quality gate.

ESLint MUST be configured with `--max-warnings 0` to enforce strict quality standards. All warnings must be addressed before code can be merged.

#### Scenario: React Hooks dependency correctness
- **GIVEN** React components use useEffect hooks
- **WHEN** ESLint analyzes the code
- **THEN** all dependencies used within hooks are declared in dependency arrays
- **AND** no `react-hooks/exhaustive-deps` warnings are reported

#### Scenario: TypeScript type safety
- **GIVEN** TypeScript code uses type annotations
- **WHEN** ESLint analyzes the code
- **THEN** explicit `any` types are avoided or justified
- **AND** no `@typescript-eslint/no-explicit-any` warnings are reported
- **AND** proper interfaces or types are used instead

#### Scenario: Frontend build with zero warnings
- **GIVEN** frontend code exists in src/ directory
- **WHEN** `npm run lint` is executed
- **THEN** zero warnings are reported
- **AND** zero errors are reported
- **AND** the command exits with status code 0

## MODIFIED Requirements

### Requirement: CI Quality Gate Enforcement
The CI pipeline SHALL enforce comprehensive quality checks before allowing code to be merged.

**Previous behavior:** Quality checks were advisory and could be bypassed.

**New behavior:** All quality gates are mandatory and must pass:
- Lightning quality check (critical Ruff errors: F821, F401, F841, E902)
- Black formatting check (zero violations)
- ESLint warnings (zero warnings, was configurable)
- TypeScript compilation (zero errors)
- Bandit critical security issues (zero HIGH severity)

#### Scenario: Lightning quality gate
- **GIVEN** code changes are pushed to CI
- **WHEN** the lightning quality check runs
- **THEN** zero critical Ruff violations (F821, F401, F841, E902) are found
- **AND** this check completes in under 3 minutes

#### Scenario: Formatting gate
- **GIVEN** code changes include Python files
- **WHEN** the formatting check runs
- **THEN** Black reports zero files needing reformatting
- **AND** the formatting gate passes

#### Scenario: TypeScript compilation gate
- **GIVEN** code changes include TypeScript files
- **WHEN** the TypeScript compiler runs with `tsc --noEmit`
- **THEN** zero type errors are reported
- **AND** the TypeScript gate passes

#### Scenario: Frontend lint gate
- **GIVEN** code changes include frontend files
- **WHEN** ESLint runs with `--max-warnings 0`
- **THEN** zero warnings are reported
- **AND** the lint gate passes

#### Scenario: Combined quality gates
- **GIVEN** all quality gates are configured
- **WHEN** a PR is submitted
- **THEN** all gates must pass for CI to succeed
- **AND** failing any gate blocks the merge
- **AND** developers receive clear feedback on which gate failed
