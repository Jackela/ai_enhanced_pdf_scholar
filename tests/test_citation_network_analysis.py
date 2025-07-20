"""
Citation Network Analysis Tests
Tests the enhanced network analysis functionality in CitationService.
"""

import pytest
from unittest.mock import Mock

from src.services.citation_service import CitationService
from src.database.models import CitationRelationModel


class TestCitationNetworkAnalysis:
    """Test enhanced citation network analysis functionality."""

    def setup_method(self):
        """Set up test dependencies."""
        self.citation_repo = Mock()
        self.relation_repo = Mock()
        self.service = CitationService(self.citation_repo, self.relation_repo)

    def test_build_citation_network_with_analytics(self):
        """Test building citation network with enhanced analytics."""
        # Mock network data from repository
        mock_network = {
            'nodes': [
                {'id': 1, 'title': 'Document 1', 'created_at': '2023-01-01'},
                {'id': 2, 'title': 'Document 2', 'created_at': '2023-02-01'},
                {'id': 3, 'title': 'Document 3', 'created_at': '2023-03-01'}
            ],
            'edges': [
                {'source': 1, 'target': 2, 'type': 'cites', 'confidence': 0.9},
                {'source': 1, 'target': 3, 'type': 'cites', 'confidence': 0.8},
                {'source': 2, 'target': 3, 'type': 'cites', 'confidence': 0.7}
            ],
            'total_nodes': 3,
            'total_edges': 3
        }
        
        self.relation_repo.get_citation_network.return_value = mock_network
        
        # Test network building
        result = self.service.build_citation_network(1, depth=2)
        
        # Verify base network data
        assert result['total_nodes'] == 3
        assert result['total_edges'] == 3
        
        # Verify enhanced analytics are added
        assert 'analytics' in result
        assert 'influential_documents' in result
        assert 'node_metrics' in result
        assert 'edge_metrics' in result
        
        # Verify analytics structure
        analytics = result['analytics']
        assert 'network_size' in analytics
        assert 'density' in analytics
        assert 'citation_patterns' in analytics
        assert 'centrality_measures' in analytics

    def test_network_metrics_calculation(self):
        """Test network metrics calculation."""
        mock_network = {
            'nodes': [
                {'id': 1, 'title': 'Central Doc'},
                {'id': 2, 'title': 'Citing Doc'},
                {'id': 3, 'title': 'Cited Doc'}
            ],
            'edges': [
                {'source': 2, 'target': 1, 'type': 'cites', 'confidence': 0.9},
                {'source': 1, 'target': 3, 'type': 'cites', 'confidence': 0.8}
            ]
        }
        
        enhanced = self.service._enhance_network_with_metrics(mock_network)
        
        # Verify node metrics
        assert 'node_metrics' in enhanced
        node_metrics = enhanced['node_metrics']
        
        # Document 1 should have in_degree=1, out_degree=1
        assert node_metrics[1]['in_degree'] == 1
        assert node_metrics[1]['out_degree'] == 1
        assert node_metrics[1]['total_degree'] == 2
        
        # Document 2 should have in_degree=0, out_degree=1
        assert node_metrics[2]['in_degree'] == 0
        assert node_metrics[2]['out_degree'] == 1
        
        # Verify edge metrics
        assert 'edge_metrics' in enhanced
        edge_metrics = enhanced['edge_metrics']
        assert 'avg_confidence' in edge_metrics
        assert abs(edge_metrics['avg_confidence'] - 0.85) < 0.001  # (0.9 + 0.8) / 2

    def test_influential_documents_identification(self):
        """Test identification of influential documents."""
        mock_network = {
            'nodes': [
                {'id': 1, 'title': 'Highly Cited Paper'},
                {'id': 2, 'title': 'Regular Paper'},
                {'id': 3, 'title': 'Recent Paper'}
            ],
            'node_metrics': {
                1: {'in_degree': 5, 'out_degree': 2, 'total_degree': 7},
                2: {'in_degree': 1, 'out_degree': 3, 'total_degree': 4},
                3: {'in_degree': 0, 'out_degree': 1, 'total_degree': 1}
            }
        }
        
        influential = self.service._identify_influential_documents(mock_network)
        
        # Should return list sorted by influence score
        assert len(influential) == 3
        
        # Document 1 should be most influential (5*2 + 2*0.5 = 11.0)
        assert influential[0]['document_id'] == 1
        assert influential[0]['influence_score'] == 11.0
        assert influential[0]['times_cited'] == 5
        
        # Document 2 should be second (1*2 + 3*0.5 = 3.5)
        assert influential[1]['document_id'] == 2
        assert influential[1]['influence_score'] == 3.5

    def test_citation_pattern_analysis(self):
        """Test citation pattern analysis."""
        edges = [
            {'type': 'cites', 'confidence': 0.9},
            {'type': 'cites', 'confidence': 0.8},
            {'type': 'references', 'confidence': 0.6},
            {'type': 'cites', 'confidence': 0.4}
        ]
        
        patterns = self.service._analyze_citation_patterns(edges)
        
        # Verify pattern analysis
        assert patterns['pattern_count'] == 4
        assert patterns['relation_types']['cites'] == 3
        assert patterns['relation_types']['references'] == 1
        assert patterns['dominant_relation_type'] == 'cites'
        
        # Verify confidence distribution
        confidence_dist = patterns['confidence_distribution']
        assert confidence_dist['high'] == 2  # >= 0.8
        assert confidence_dist['medium'] == 1  # 0.5-0.8
        assert confidence_dist['low'] == 1  # < 0.5

    def test_temporal_pattern_analysis(self):
        """Test temporal pattern analysis."""
        nodes = [
            {'id': 1, 'created_at': '2020-01-01'},
            {'id': 2, 'created_at': '2021-06-01'},
            {'id': 3, 'created_at': '2023-12-01'}
        ]
        
        temporal = self.service._analyze_temporal_patterns(nodes)
        
        # Verify temporal analysis
        assert temporal['temporal_span'] == 3
        assert temporal['earliest_document'] == '2020-01-01'
        assert temporal['latest_document'] == '2023-12-01'
        assert '2020-01-01 to 2023-12-01' in temporal['date_coverage']

    def test_centrality_measures_calculation(self):
        """Test centrality measures calculation."""
        mock_network = {
            'node_metrics': {
                1: {'total_degree': 4},
                2: {'total_degree': 2},
                3: {'total_degree': 1}
            }
        }
        
        centrality = self.service._calculate_centrality_measures(mock_network)
        
        # Verify centrality calculation
        assert centrality['centrality_calculated'] is True
        assert 'degree_centrality' in centrality
        
        # With 3 nodes, max degree is 2, so:
        # Node 1: 4/2 = 2.0 (capped at 1.0 in practice)
        # Node 2: 2/2 = 1.0  
        # Node 3: 1/2 = 0.5
        degree_centrality = centrality['degree_centrality']
        assert degree_centrality[2] == 1.0
        assert degree_centrality[3] == 0.5
        
        # Verify most central nodes
        most_central = centrality['most_central_nodes']
        assert len(most_central) <= 5
        assert most_central[0]['node_id'] == 1  # Highest centrality first

    def test_citation_recommendations(self):
        """Test citation recommendation generation."""
        # Mock network building
        mock_network = {
            'nodes': [{'id': 1}, {'id': 2}],
            'edges': [],
            'analytics': {},
            'influential_documents': []
        }
        
        self.relation_repo.get_citation_network.return_value = mock_network
        self.relation_repo.get_relations_by_source.return_value = []
        
        recommendations = self.service.get_citation_recommendations(1, limit=5)
        
        # Should return list (may be empty if no similar documents found)
        assert isinstance(recommendations, list)
        assert len(recommendations) <= 5

    def test_citation_cluster_detection(self):
        """Test citation cluster detection."""
        # Mock citation relations
        mock_relations = [
            Mock(source_document_id=1, target_document_id=2),
            Mock(source_document_id=2, target_document_id=3),
            Mock(source_document_id=3, target_document_id=1),  # Forms a cluster
            Mock(source_document_id=4, target_document_id=5),
            Mock(source_document_id=5, target_document_id=4)   # Forms another cluster
        ]
        
        self.relation_repo.get_all_relations.return_value = mock_relations
        
        clusters = self.service.detect_citation_clusters(min_cluster_size=2)
        
        # Should detect clusters
        assert isinstance(clusters, list)
        
        # Verify cluster structure
        for cluster in clusters:
            assert 'cluster_id' in cluster
            assert 'document_ids' in cluster
            assert 'size' in cluster
            assert cluster['size'] >= 2  # Minimum cluster size

    def test_network_analytics_with_empty_network(self):
        """Test network analytics with empty network."""
        empty_network = {'nodes': [], 'edges': []}
        
        analytics = self.service._calculate_network_analytics(empty_network)
        
        # Should handle empty network gracefully
        assert analytics['network_size'] == 0
        assert analytics['connection_count'] == 0
        assert analytics['density'] == 0.0
        assert analytics['avg_degree'] == 0.0

    def test_network_depth_validation(self):
        """Test network depth validation."""
        self.relation_repo.get_citation_network.return_value = {'nodes': [], 'edges': []}
        
        # Valid depths should work
        result = self.service.build_citation_network(1, depth=1)
        assert isinstance(result, dict)
        
        result = self.service.build_citation_network(1, depth=3)
        assert isinstance(result, dict)
        
        # Invalid depths should raise ValueError
        with pytest.raises(ValueError, match="Depth must be between 1 and 3"):
            self.service.build_citation_network(1, depth=0)
        
        with pytest.raises(ValueError, match="Depth must be between 1 and 3"):
            self.service.build_citation_network(1, depth=4)

    def test_error_handling_in_network_analysis(self):
        """Test error handling in network analysis methods."""
        # Test with malformed network data
        malformed_network = {'nodes': [{'invalid': 'data'}], 'edges': []}
        
        # Should not crash, should return graceful defaults
        enhanced = self.service._enhance_network_with_metrics(malformed_network)
        assert isinstance(enhanced, dict)
        
        analytics = self.service._calculate_network_analytics(malformed_network)
        assert isinstance(analytics, dict)
        
        influential = self.service._identify_influential_documents(malformed_network)
        assert isinstance(influential, list)

    def test_performance_with_large_network(self):
        """Test performance with moderately large network."""
        import time
        
        # Create a moderately large network
        large_network = {
            'nodes': [{'id': i, 'title': f'Doc {i}'} for i in range(100)],
            'edges': [
                {'source': i, 'target': (i + 1) % 100, 'type': 'cites', 'confidence': 0.8}
                for i in range(100)
            ]
        }
        
        start_time = time.time()
        enhanced = self.service._enhance_network_with_metrics(large_network)
        analytics = self.service._calculate_network_analytics(enhanced)
        influential = self.service._identify_influential_documents(enhanced)
        processing_time = time.time() - start_time
        
        # Should complete within reasonable time (< 1 second for 100 nodes)
        assert processing_time < 1.0
        
        # Should return valid results
        assert len(enhanced['node_metrics']) == 100
        assert isinstance(analytics, dict)
        assert isinstance(influential, list)
        assert len(influential) <= 10  # Top 10 influential documents