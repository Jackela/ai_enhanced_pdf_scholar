# 1. Database Selection: Relational DB vs. NoSQL

- **Status:** Accepted
- **Date:** 2025-08-15

## Context

The AI Enhanced PDF Scholar platform requires a persistent data store to manage user accounts, document metadata (e.g., title, authors, upload date), and relationships between documents (e.g., citations). The integrity and consistency of this data are critical for the platform's reliability. We need to choose a primary database technology that can meet our current needs and scale for future growth.

The main decision point is between a traditional **Relational Database (SQL)** like PostgreSQL and a **NoSQL Document Store** like MongoDB.

## Decision

We have decided to use **PostgreSQL** as our primary database.

For development and simple deployments, this will be implemented via **SQLite** for its ease of use, with a clear and tested migration path to a full PostgreSQL instance for production environments.

## Consequences

### Positive:
- **Data Integrity and Consistency:** By enforcing a schema and using ACID transactions, PostgreSQL ensures that our user and document data remains consistent and reliable. This is crucial for features like user authentication and managing document ownership.
- **Structured for Relational Data:** Our data model is inherently relational (users have documents, documents have citations, citations link to other documents). PostgreSQL is purpose-built for querying this type of structured, related data efficiently.
- **Mature Ecosystem:** PostgreSQL is a battle-tested database with a vast ecosystem of tools for backups, monitoring, and performance analysis. It also has broad support in cloud environments (e.g., AWS RDS, Google Cloud SQL).
- **Powerful Querying:** SQL provides a powerful and standardized language for complex queries, which will be beneficial as we build more advanced analytics and reporting features.

### Negative (Trade-offs):
- **Reduced Flexibility:** We lose the schema flexibility of a NoSQL database like MongoDB. Changes to the data model will require structured migrations, which can be more complex to manage than simply adding new fields to a JSON document.
- **Scaling Complexity:** While PostgreSQL can scale significantly, horizontal scaling (sharding) is generally more complex to implement compared to many No-SQL databases that are designed for it from the ground up. However, for our expected scale in the medium term, vertical scaling and read replicas will be more than sufficient.
- **Not Ideal for Unstructured Data:** While PostgreSQL has good JSON support, it is not the primary storage solution for the *content* of the PDFs themselves or for the vector embeddings. These are handled by a separate file storage system and a specialized Vector Store, respectively. This ADR applies only to the structured metadata.
