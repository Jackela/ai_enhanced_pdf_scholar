# Code Complexity Specification

## ADDED Requirements

### Requirement: Maximum Function Complexity
Functions SHALL NOT exceed a cyclomatic complexity of 10.

McCabe complexity measures the number of independent execution paths through code. High complexity indicates functions that are difficult to test, understand, and maintain.

#### Scenario: Function complexity within limits
- **GIVEN** a function is being written or refactored
- **WHEN** static analysis tools measure complexity
- **THEN** the McCabe complexity score is ≤ 10
- **AND** the function has a single, clear responsibility

#### Scenario: Complex function refactoring
- **GIVEN** a function exceeds complexity 10
- **WHEN** refactoring the function
- **THEN** logic is extracted into focused helper functions
- **AND** each helper has complexity ≤ 10
- **AND** the main function orchestrates calls to helpers

#### Scenario: Early return pattern
- **GIVEN** a function has multiple error conditions
- **WHEN** handling error cases
- **THEN** early returns are used to reduce nesting
- **AND** the happy path has minimal indentation
- **AND** complexity is reduced through guard clauses

### Requirement: Helper Function Extraction
Complex logic SHALL be decomposed into focused, testable helper functions.

When a function grows complex, related logic should be extracted into helper functions with clear names and single responsibilities.

#### Scenario: Strategy pattern for conditionals
- **GIVEN** a function has complex conditional logic
- **WHEN** refactoring
- **THEN** strategies are implemented as separate functions or classes
- **AND** a dispatch mechanism selects the appropriate strategy
- **AND** each strategy has low complexity

#### Scenario: Health check aggregation
- **GIVEN** a function aggregates multiple health checks
- **WHEN** implementing the function
- **THEN** each health check is a separate function
- **AND** results are collected and aggregated in the main function
- **AND** the main function has minimal complexity
