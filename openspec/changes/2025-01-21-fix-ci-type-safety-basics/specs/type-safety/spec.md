# Type Safety Specification - Basics

## ADDED Requirements

### Requirement: Function Type Annotations
All functions SHALL have complete type annotations for parameters and return values.

#### Scenario: Typed function signature
- **GIVEN** a function is defined
- **WHEN** mypy analyzes the code
- **THEN** all parameters have type hints
- **AND** the return type is annotated
- **AND** no no-untyped-def error occurs

### Requirement: Generic Type Parameters
Generic types SHALL specify their element types.

#### Scenario: Tuple with type parameters
- **GIVEN** a function returns a tuple
- **WHEN** declaring the return type
- **THEN** tuple element types are specified: `tuple[int, str]`
- **AND** no type-arg error occurs

### Requirement: No Dead Code
Code SHALL NOT contain unreachable statements.

#### Scenario: Code after return
- **GIVEN** a function has a return statement
- **WHEN** code follows the return
- **THEN** the unreachable code is removed
- **AND** no unreachable error occurs
