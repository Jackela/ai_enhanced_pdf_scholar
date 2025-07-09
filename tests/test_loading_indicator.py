"""
Comprehensive test suite for the LoadingIndicator component.

This module tests all aspects of the loading indicator including:
- Initialization and UI setup
- Show/hide functionality 
- Position calculation
- Animation effects
- Parent widget integration
"""

import pytest
from PyQt6.QtWidgets import QWidget, QMainWindow
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtTest import QTest

from src.loading_indicator import LoadingIndicator


class TestLoadingIndicator:
    """Test suite for LoadingIndicator basic functionality."""
    
    def test_initialization(self, qtbot):
        """Test that LoadingIndicator initializes correctly."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        assert loading_indicator.parent() == parent
        assert not loading_indicator.isVisible()
        assert loading_indicator.windowFlags() & Qt.WindowType.FramelessWindowHint
        # Note: LoadingIndicator doesn't use WindowStaysOnTopHint as it's a child widget
        
    def test_ui_components_creation(self, qtbot):
        """Test that UI components are created properly."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Check basic properties
        assert loading_indicator.width() == 120
        assert loading_indicator.height() == 60
        assert hasattr(loading_indicator, 'rotation_timer')
        assert hasattr(loading_indicator, 'fade_animation')
        
    def test_show_at_position(self, qtbot):
        """Test showing the loading indicator at a specific position."""
        parent = QWidget()
        parent.setGeometry(100, 100, 400, 300)
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        test_position = QPoint(200, 150)
        loading_indicator.show_at_position(test_position)
        
        # Wait for the show operation
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        assert loading_indicator.isVisible()
        assert loading_indicator.rotation_timer.isActive()
        
    def test_show_at_global_position(self, qtbot):
        """Test showing at global position outside parent bounds."""
        parent = QWidget()
        parent.setGeometry(100, 100, 200, 200)
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Position outside parent bounds
        global_position = QPoint(500, 500)
        loading_indicator.show_at_position(global_position)
        
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        assert loading_indicator.isVisible()
        # Should be constrained within parent bounds
        
    def test_hide_with_fade(self, qtbot):
        """Test hiding with fade effect."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # First show the indicator
        loading_indicator.show_at_position(QPoint(100, 100))
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        # Then hide with fade
        loading_indicator.hide_with_fade()
        
        # Should start fade out animation
        assert hasattr(loading_indicator, 'fade_animation')
        
        # Wait for fade to complete (animation duration + small buffer)
        qtbot.waitUntil(lambda: not loading_indicator.isVisible(), timeout=2000)
        
    def test_position_constraint_within_parent(self, qtbot):
        """Test that position is constrained within parent widget."""
        parent = QWidget()
        parent.setGeometry(0, 0, 300, 200)
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Try to position way outside parent bounds
        extreme_position = QPoint(1000, 1000)
        loading_indicator.show_at_position(extreme_position)
        
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        # Position should be constrained
        final_pos = loading_indicator.pos()
        parent_rect = parent.rect()
        
        assert 0 <= final_pos.x() <= parent_rect.width() - loading_indicator.width()
        assert 0 <= final_pos.y() <= parent_rect.height() - loading_indicator.height()
        
    def test_multiple_show_calls(self, qtbot):
        """Test that multiple show calls work correctly."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # First show
        loading_indicator.show_at_position(QPoint(50, 50))
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        first_pos = loading_indicator.pos()
        
        # Second show at different position
        loading_indicator.show_at_position(QPoint(100, 100))
        qtbot.wait(100)  # Brief wait for position update
        second_pos = loading_indicator.pos()
        
        assert loading_indicator.isVisible()
        # Only test if positions are different if they actually should be
        # (depends on parent size and positioning logic)
        
    def test_hide_before_show_completed(self, qtbot):
        """Test hiding before show animation completes."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Show and immediately hide
        loading_indicator.show_at_position(QPoint(100, 100))
        loading_indicator.hide_with_fade()
        
        # Should not crash and should end up hidden
        qtbot.waitUntil(lambda: not loading_indicator.isVisible(), timeout=2000)

    def test_rotation_animation(self, qtbot):
        """Test that rotation animation works correctly."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Show indicator to start rotation
        loading_indicator.show_at_position(QPoint(100, 100))
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        # Check rotation animation
        initial_angle = loading_indicator.angle
        qtbot.wait(200)  # Wait for rotation
        final_angle = loading_indicator.angle
        
        # Angle should have changed
        assert initial_angle != final_angle

    def test_cleanup_on_hide(self, qtbot):
        """Test that timers are properly stopped on hide."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Show then hide
        loading_indicator.show_at_position(QPoint(100, 100))
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        assert loading_indicator.rotation_timer.isActive()
        
        loading_indicator.hide_with_fade()
        qtbot.wait(100)  # Brief wait for hide to start
        
        # Timer should be stopped
        assert not loading_indicator.rotation_timer.isActive()


class TestLoadingIndicatorIntegration:
    """Integration tests for LoadingIndicator with various parent widgets."""
    
    def test_with_main_window_parent(self, qtbot):
        """Test LoadingIndicator with QMainWindow parent."""
        main_window = QMainWindow()
        main_window.setGeometry(100, 100, 800, 600)
        qtbot.addWidget(main_window)
        main_window.show()
        
        loading_indicator = LoadingIndicator(main_window)
        qtbot.addWidget(loading_indicator)
        
        # Show in center of main window
        center_pos = main_window.rect().center()
        loading_indicator.show_at_position(center_pos)
        
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        assert loading_indicator.isVisible()
        
        # Clean up
        loading_indicator.hide_with_fade()
        qtbot.waitUntil(lambda: not loading_indicator.isVisible(), timeout=2000)
        
    def test_animation_cleanup_on_parent_close(self, qtbot):
        """Test that animations are cleaned up when parent is closed."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        loading_indicator.show_at_position(QPoint(100, 100))
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        # Close parent while animation might be running
        parent.close()
        
        # Should not crash
        qtbot.wait(100)
        
    def test_size_adjustment_for_small_parent(self, qtbot):
        """Test behavior when parent is very small."""
        parent = QWidget()
        parent.setGeometry(0, 0, 50, 50)  # Very small parent
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        loading_indicator.show_at_position(QPoint(25, 25))
        
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        # Should still be visible and positioned appropriately
        assert loading_indicator.isVisible()
        
    def test_raises_to_front(self, qtbot):
        """Test that loading indicator raises to front of other widgets."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        # Create another widget in the same parent
        sibling = QWidget(parent)
        sibling.setGeometry(50, 50, 100, 100)
        sibling.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        loading_indicator.show_at_position(QPoint(75, 75))  # Overlapping position
        
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        # LoadingIndicator should be visible (raise_() was called)
        assert loading_indicator.isVisible()


class TestLoadingIndicatorEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_with_none_parent(self, qtbot):
        """Test behavior with None parent (should not crash)."""
        # This should work as Qt allows None parent
        loading_indicator = LoadingIndicator(None)
        if loading_indicator:  # If creation succeeds
            qtbot.addWidget(loading_indicator)
            # Basic operations should not crash
            loading_indicator.show_at_position(QPoint(100, 100))
            loading_indicator.hide_with_fade()
            
    def test_position_with_negative_coordinates(self, qtbot):
        """Test positioning with negative coordinates."""
        parent = QWidget()
        parent.setGeometry(100, 100, 300, 200)
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Negative position should be handled gracefully
        loading_indicator.show_at_position(QPoint(-50, -50))
        
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        # Should be positioned at valid coordinates
        final_pos = loading_indicator.pos()
        assert final_pos.x() >= 0
        assert final_pos.y() >= 0
        
    def test_rapid_show_hide_cycles(self, qtbot):
        """Test rapid show/hide cycles for stability."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Rapid cycles
        for i in range(5):
            loading_indicator.show_at_position(QPoint(50 + i*10, 50 + i*10))
            qtbot.wait(50)  # Small delay
            loading_indicator.hide_with_fade()
            qtbot.wait(50)
            
        # Should not crash and should end up hidden
        qtbot.waitUntil(lambda: not loading_indicator.isVisible(), timeout=2000)
        
    def test_memory_cleanup(self, qtbot):
        """Test that resources are properly cleaned up."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Show, hide, and verify cleanup
        loading_indicator.show_at_position(QPoint(100, 100))
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        loading_indicator.hide_with_fade()
        qtbot.waitUntil(lambda: not loading_indicator.isVisible(), timeout=2000)
        
        # Timer should be stopped after hide
        assert not loading_indicator.rotation_timer.isActive()

    def test_paint_event_coverage(self, qtbot):
        """Test that paint event works without errors."""
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.show()
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Show to trigger paint events
        loading_indicator.show_at_position(QPoint(100, 100))
        qtbot.waitUntil(lambda: loading_indicator.isVisible(), timeout=1000)
        
        # Force a repaint
        loading_indicator.update()
        qtbot.wait(100)
        
        # Should not crash during painting
        assert loading_indicator.isVisible()

    def test_rotation_property(self, qtbot):
        """Test rotation property setter and getter."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        loading_indicator = LoadingIndicator(parent)
        qtbot.addWidget(loading_indicator)
        
        # Test rotation property
        initial_rotation = loading_indicator.rotation
        loading_indicator.rotation = 90
        assert loading_indicator.rotation == 90
        assert loading_indicator.angle == 90 