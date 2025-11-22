# Type Safety Specification - Unions

## MODIFIED Requirements

### Requirement: Optional Type Handling
Optional types SHALL be checked for None before attribute access.

#### Scenario: Safe attribute access
- **GIVEN** a variable has type `str | None`
- **WHEN** accessing an attribute
- **THEN** a None check precedes the access
- **AND** no union-attr error occurs

### Requirement: Attribute Existence
Classes SHALL define all accessed attributes.

#### Scenario: Defined attributes
- **GIVEN** code accesses an attribute on an object
- **WHEN** mypy analyzes the code
- **THEN** the attribute is defined in the class
- **AND** no attr-defined error occurs
