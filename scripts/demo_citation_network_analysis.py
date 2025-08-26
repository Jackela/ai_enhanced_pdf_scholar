#!/usr/bin/env python3
"""
Citation Network Analysis Demo Script
Demonstrates the enhanced citation network analysis capabilities.
"""

import json
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import DatabaseConnection
from src.database.models import CitationModel, CitationRelationModel, DocumentModel
from src.database.modular_migrator import ModularDatabaseMigrator as DatabaseMigrator
from src.repositories.citation_relation_repository import CitationRelationRepository
from src.repositories.citation_repository import CitationRepository
from src.repositories.document_repository import DocumentRepository
from src.services.citation_service import CitationService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_demo_data(db_connection: DatabaseConnection) -> dict[str, int]:
    """
    Create demo data for citation network analysis.

    Args:
        db_connection: Database connection

    Returns:
        Dictionary mapping document names to IDs
    """
    logger.info("Creating demo citation network data...")

    # Create repositories
    doc_repo = DocumentRepository(db_connection)
    citation_repo = CitationRepository(db_connection)
    relation_repo = CitationRelationRepository(db_connection)

    # Create sample documents
    documents = [
        {
            "title": "Attention Is All You Need",
            "authors": "Vaswani et al.",
            "year": 2017,
            "description": "Seminal transformer architecture paper"
        },
        {
            "title": "BERT: Pre-training Deep Bidirectional Transformers",
            "authors": "Devlin et al.",
            "year": 2018,
            "description": "BERT language model"
        },
        {
            "title": "Language Models are Few-Shot Learners",
            "authors": "Brown et al.",
            "year": 2020,
            "description": "GPT-3 paper"
        },
        {
            "title": "Training Language Models to Follow Instructions",
            "authors": "Ouyang et al.",
            "year": 2022,
            "description": "InstructGPT paper"
        },
        {
            "title": "Constitutional AI: Harmlessness from AI Feedback",
            "authors": "Bai et al.",
            "year": 2022,
            "description": "Constitutional AI paper"
        }
    ]

    doc_ids = {}
    created_docs = []

    # Create documents
    for i, doc_info in enumerate(documents):
        document = DocumentModel(
            title=doc_info["title"],
            file_path=f"/demo/papers/{doc_info['title'].lower().replace(' ', '_')}.pdf",
            file_hash=f"demo_hash_{i+1}",
            file_size=1024000 + i * 100000,
            content_hash=f"content_hash_{i+1}",
            page_count=10 + i * 2,
            _from_database=False
        )

        # Insert document
        insert_sql = """
            INSERT INTO documents (title, file_path, file_hash, file_size, content_hash, page_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """
        db_connection.execute(insert_sql, (
            document.title, document.file_path, document.file_hash,
            document.file_size, document.content_hash, document.page_count
        ))

        # Get generated ID
        row = db_connection.fetch_one("SELECT id FROM documents WHERE file_hash = ?", (document.file_hash,))
        if row:
            document.id = row["id"]
            doc_ids[doc_info["title"]] = document.id
            created_docs.append(document)

    # Create citations within documents
    citation_data = [
        # Transformer paper citations
        {
            "document_id": doc_ids["Attention Is All You Need"],
            "raw_text": "LeCun, Y., Bengio, Y., & Hinton, G. (2015). Deep learning. Nature, 521(7553), 436-444.",
            "authors": "LeCun, Y.",
            "title": "Deep learning",
            "publication_year": 2015,
            "journal_or_venue": "Nature",
            "citation_type": "journal"
        },
        # BERT paper citations
        {
            "document_id": doc_ids["BERT: Pre-training Deep Bidirectional Transformers"],
            "raw_text": "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., ... & Polosukhin, I. (2017). Attention is all you need.",
            "authors": "Vaswani, A.",
            "title": "Attention is all you need",
            "publication_year": 2017,
            "citation_type": "conference"
        },
        # GPT-3 paper citations
        {
            "document_id": doc_ids["Language Models are Few-Shot Learners"],
            "raw_text": "Vaswani, A. et al. (2017). Attention is all you need. In Advances in neural information processing systems.",
            "authors": "Vaswani, A.",
            "title": "Attention is all you need",
            "publication_year": 2017,
            "citation_type": "conference"
        },
        {
            "document_id": doc_ids["Language Models are Few-Shot Learners"],
            "raw_text": "Devlin, J., Chang, M. W., Lee, K., & Toutanova, K. (2018). BERT: Pre-training of Deep Bidirectional Transformers.",
            "authors": "Devlin, J.",
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "publication_year": 2018,
            "citation_type": "preprint"
        },
        # InstructGPT citations
        {
            "document_id": doc_ids["Training Language Models to Follow Instructions"],
            "raw_text": "Brown, T., Mann, B., Ryder, N., Subbiah, M., Kaplan, J., Dhariwal, P., ... & Amodei, D. (2020). Language models are few-shot learners.",
            "authors": "Brown, T.",
            "title": "Language models are few-shot learners",
            "publication_year": 2020,
            "citation_type": "conference"
        },
        # Constitutional AI citations
        {
            "document_id": doc_ids["Constitutional AI: Harmlessness from AI Feedback"],
            "raw_text": "Ouyang, L., Wu, J., Jiang, X., Almeida, D., Wainwright, C. L., Mishkin, P., ... & Lowe, R. (2022). Training language models to follow instructions with human feedback.",
            "authors": "Ouyang, L.",
            "title": "Training language models to follow instructions with human feedback",
            "publication_year": 2022,
            "citation_type": "preprint"
        }
    ]

    citation_ids = {}

    # Create citations
    for cit_data in citation_data:
        citation = CitationModel(
            document_id=cit_data["document_id"],
            raw_text=cit_data["raw_text"],
            authors=cit_data.get("authors"),
            title=cit_data.get("title"),
            publication_year=cit_data.get("publication_year"),
            journal_or_venue=cit_data.get("journal_or_venue"),
            citation_type=cit_data.get("citation_type", "unknown"),
            confidence_score=0.9
        )

        created_citation = citation_repo.create(citation)
        citation_key = f"{cit_data['document_id']}_{cit_data.get('title', 'unknown')}"
        citation_ids[citation_key] = created_citation.id

    # Create citation relations (cross-document references)
    relations = [
        # BERT cites Transformer
        {
            "source_doc": "BERT: Pre-training Deep Bidirectional Transformers",
            "target_doc": "Attention Is All You Need",
            "relation_type": "cites",
            "confidence": 0.95
        },
        # GPT-3 cites both Transformer and BERT
        {
            "source_doc": "Language Models are Few-Shot Learners",
            "target_doc": "Attention Is All You Need",
            "relation_type": "cites",
            "confidence": 0.90
        },
        {
            "source_doc": "Language Models are Few-Shot Learners",
            "target_doc": "BERT: Pre-training Deep Bidirectional Transformers",
            "relation_type": "cites",
            "confidence": 0.85
        },
        # InstructGPT cites GPT-3
        {
            "source_doc": "Training Language Models to Follow Instructions",
            "target_doc": "Language Models are Few-Shot Learners",
            "relation_type": "builds_on",
            "confidence": 0.95
        },
        # Constitutional AI cites InstructGPT
        {
            "source_doc": "Constitutional AI: Harmlessness from AI Feedback",
            "target_doc": "Training Language Models to Follow Instructions",
            "relation_type": "extends",
            "confidence": 0.90
        }
    ]

    # Create citation relations
    for rel_data in relations:
        source_id = doc_ids[rel_data["source_doc"]]
        target_id = doc_ids[rel_data["target_doc"]]

        # Find a citation in source document (use first available)
        source_citations = citation_repo.find_by_document_id(source_id)
        source_citation_id = source_citations[0].id if source_citations else None

        relation = CitationRelationModel(
            source_document_id=source_id,
            source_citation_id=source_citation_id,
            target_document_id=target_id,
            relation_type=rel_data["relation_type"],
            confidence_score=rel_data["confidence"]
        )

        relation_repo.create(relation)

    logger.info(f"Created {len(documents)} documents with {len(citation_data)} citations and {len(relations)} relations")
    return doc_ids


def demonstrate_network_analysis(citation_service: CitationService, doc_ids: dict[str, int]):
    """
    Demonstrate various citation network analysis features.

    Args:
        citation_service: Citation service instance
        doc_ids: Document IDs mapping
    """
    logger.info("=== Citation Network Analysis Demo ===")

    # Demo 1: Build comprehensive citation network
    print("\\n1. Building Citation Network for 'Language Models are Few-Shot Learners' (GPT-3)")
    print("-" * 70)

    gpt3_id = doc_ids["Language Models are Few-Shot Learners"]
    network = citation_service.build_citation_network(gpt3_id, depth=2)

    print("Network Statistics:")
    print(f"  • Total Nodes: {network['total_nodes']}")
    print(f"  • Total Edges: {network['total_edges']}")
    print(f"  • Network Depth: {network['depth']}")

    # Show analytics
    if 'analytics' in network:
        analytics = network['analytics']
        print("\\nNetwork Analytics:")
        print(f"  • Density: {analytics.get('density', 0):.3f}")
        print(f"  • Average Degree: {analytics.get('avg_degree', 0):.2f}")

        if 'citation_patterns' in analytics:
            patterns = analytics['citation_patterns']
            print(f"  • Citation Patterns: {patterns.get('pattern_count', 0)} connections")
            if 'relation_types' in patterns:
                print(f"  • Relation Types: {patterns['relation_types']}")

    # Demo 2: Identify influential documents
    print("\\n2. Most Influential Documents in Network")
    print("-" * 70)

    if 'influential_documents' in network:
        influential = network['influential_documents'][:3]  # Top 3
        for i, doc in enumerate(influential, 1):
            doc_id = doc.get('document_id')
            title = doc.get('title', f'Document {doc_id}')
            print(f"{i}. {title}")
            print(f"   Influence Score: {doc.get('influence_score', 0):.1f}")
            print(f"   Times Cited: {doc.get('times_cited', 0)}")
            print(f"   Documents Cited: {doc.get('documents_cited', 0)}")

    # Demo 3: Citation recommendations
    print("\\n3. Citation Recommendations")
    print("-" * 70)

    recommendations = citation_service.get_citation_recommendations(gpt3_id, limit=3)
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. Document ID: {rec.get('document_id')}")
            print(f"   Score: {rec.get('recommendation_score', 0):.2f}")
            print(f"   Reason: {rec.get('reason')}")
    else:
        print("No recommendations available (requires more citation data)")

    # Demo 4: Citation clustering
    print("\\n4. Citation Cluster Detection")
    print("-" * 70)

    clusters = citation_service.detect_citation_clusters(min_cluster_size=2)
    if clusters:
        for cluster in clusters[:2]:  # Show first 2 clusters
            print(f"Cluster {cluster['cluster_id']}:")
            print(f"  • Size: {cluster['size']} documents")
            print(f"  • Internal Connections: {cluster['internal_connections']}")
            print(f"  • Document IDs: {cluster['document_ids']}")
    else:
        print("No significant clusters detected")

    # Demo 5: Network edge analysis
    print("\\n5. Edge Analysis")
    print("-" * 70)

    if 'edge_metrics' in network:
        edge_metrics = network['edge_metrics']
        print("Edge Confidence Statistics:")
        print(f"  • Average Confidence: {edge_metrics.get('avg_confidence', 0):.3f}")
        print(f"  • Min Confidence: {edge_metrics.get('min_confidence', 0):.3f}")
        print(f"  • Max Confidence: {edge_metrics.get('max_confidence', 0):.3f}")
        print(f"  • High Confidence Edges (≥0.8): {edge_metrics.get('high_confidence_count', 0)}")

    # Demo 6: Centrality measures
    print("\\n6. Node Centrality Analysis")
    print("-" * 70)

    if 'analytics' in network and 'centrality_measures' in network['analytics']:
        centrality = network['analytics']['centrality_measures']
        if centrality.get('centrality_calculated'):
            print(f"Average Centrality: {centrality.get('avg_centrality', 0):.3f}")

            most_central = centrality.get('most_central_nodes', [])[:3]
            print("Most Central Nodes:")
            for i, node in enumerate(most_central, 1):
                print(f"  {i}. Node {node.get('node_id')}: {node.get('centrality', 0):.3f}")


def export_network_data(network: dict, output_file: str):
    """
    Export network data to JSON for visualization.

    Args:
        network: Network data dictionary
        output_file: Output file path
    """
    logger.info(f"Exporting network data to {output_file}")

    # Prepare data for export (make it JSON serializable)
    export_data = {
        "metadata": {
            "total_nodes": network.get('total_nodes', 0),
            "total_edges": network.get('total_edges', 0),
            "center_document": network.get('center_document'),
            "depth": network.get('depth', 1)
        },
        "nodes": network.get('nodes', []),
        "edges": network.get('edges', []),
        "analytics": network.get('analytics', {}),
        "influential_documents": network.get('influential_documents', [])
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"\\n📁 Network data exported to: {output_file}")
    print("   This file can be used for network visualization tools")


def main():
    """Main demo execution."""
    logger.info("Starting Citation Network Analysis Demo")

    # Setup database
    db_path = ":memory:"  # Use in-memory database for demo
    db_connection = DatabaseConnection(db_path)

    # Run migrations
    migrator = DatabaseMigrator(db_connection)
    migrator.migrate()

    # Create demo data
    doc_ids = create_demo_data(db_connection)

    # Setup services
    citation_repo = CitationRepository(db_connection)
    relation_repo = CitationRelationRepository(db_connection)
    citation_service = CitationService(citation_repo, relation_repo)

    # Run demonstration
    demonstrate_network_analysis(citation_service, doc_ids)

    # Export sample network for visualization
    gpt3_id = doc_ids["Language Models are Few-Shot Learners"]
    network = citation_service.build_citation_network(gpt3_id, depth=2)

    output_dir = Path(__file__).parent.parent / "demo_output"
    output_dir.mkdir(exist_ok=True)
    export_file = output_dir / "citation_network_sample.json"
    export_network_data(network, str(export_file))

    print("\\n" + "="*70)
    print("🎉 Citation Network Analysis Demo Complete!")
    print("="*70)
    print("\\nFeatures demonstrated:")
    print("✅ Enhanced network building with metrics")
    print("✅ Influential document identification")
    print("✅ Citation recommendation system")
    print("✅ Citation cluster detection")
    print("✅ Network analytics and centrality measures")
    print("✅ Data export for visualization")
    print("\\nNext steps:")
    print("🔗 Integrate with web API endpoints")
    print("🎨 Build React frontend visualization")
    print("⚡ Optimize performance for large networks")


if __name__ == "__main__":
    main()
