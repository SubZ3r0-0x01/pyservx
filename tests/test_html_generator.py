#!/usr/bin/env python3
"""
Tests for HTML Generator with Glass Theme Shadow System
"""

import unittest
import os
import tempfile
from unittest.mock import Mock, patch
from pyservx.html_generator import list_directory_page


class TestHTMLGeneratorShadows(unittest.TestCase):
    """Test suite for verifying multi-layer shadow system in HTML generator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_file_explorer_has_multi_layer_shadows(self):
        """Test that file explorer panel has green depth shadows, black elevation shadows, and inset highlights."""
        handler = Mock()
        handler.path = '/'
        
        html_output = list_directory_page(handler, self.temp_dir)
        
        # Verify file explorer has multi-layer shadows
        self.assertIn('box-shadow: 0 8px 32px rgba(0, 255, 0, 0.1)', html_output)
        self.assertIn('0 2px 8px rgba(0, 0, 0, 0.3)', html_output)
        self.assertIn('inset 0 1px 0 rgba(255, 255, 255, 0.1)', html_output)
    
    def test_text_panel_has_multi_layer_shadows(self):
        """Test that text panel has appropriate shadow effects."""
        handler = Mock()
        handler.path = '/'
        
        html_output = list_directory_page(handler, self.temp_dir)
        
        # Verify text panel has multi-layer shadows
        self.assertIn('.text-panel', html_output)
        self.assertIn('box-shadow: 0 8px 32px rgba(0, 255, 0, 0.1)', html_output)
    
    def test_input_elements_have_inset_shadows(self):
        """Test that input elements have inset shadows for depth."""
        handler = Mock()
        handler.path = '/'
        
        html_output = list_directory_page(handler, self.temp_dir)
        
        # Verify inputs have inset shadows
        self.assertIn('box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3)', html_output)
    
    def test_button_hover_has_enhanced_shadows(self):
        """Test that button hover states have enhanced shadow effects."""
        handler = Mock()
        handler.path = '/'
        
        html_output = list_directory_page(handler, self.temp_dir)
        
        # Verify button hover has enhanced shadows
        self.assertIn('button:hover', html_output)
        self.assertIn('box-shadow: 0 6px 24px rgba(0, 255, 0, 0.25)', html_output)
        self.assertIn('0 0 20px rgba(0, 255, 0, 0.3)', html_output)
    
    def test_table_has_glass_shadows(self):
        """Test that table elements have glass effect shadows."""
        handler = Mock()
        handler.path = '/'
        
        html_output = list_directory_page(handler, self.temp_dir)
        
        # Verify table has glass shadows
        self.assertIn('table {', html_output)
        # Check for multi-layer shadow in table styles
        table_section = html_output[html_output.find('/* Table Styles */'):html_output.find('/* Table Styles */')+500]
        self.assertIn('box-shadow:', table_section)
    
    def test_focus_states_have_layered_shadows(self):
        """Test that focus states have multi-layer shadow effects."""
        handler = Mock()
        handler.path = '/'
        
        html_output = list_directory_page(handler, self.temp_dir)
        
        # Verify focus states have layered shadows
        self.assertIn('input:focus, textarea:focus', html_output)
        self.assertIn('0 0 0 3px rgba(0, 255, 0, 0.15)', html_output)
        self.assertIn('0 0 20px rgba(0, 255, 0, 0.2)', html_output)
    
    def test_light_theme_has_adapted_shadows(self):
        """Test that light theme has appropriately adapted shadow colors."""
        handler = Mock()
        handler.path = '/'
        
        html_output = list_directory_page(handler, self.temp_dir)
        
        # Verify light theme has adapted shadows
        self.assertIn('body.light-theme', html_output)
        # Light theme should have different shadow intensities
        light_theme_section = html_output[html_output.find('body.light-theme input'):]
        self.assertIn('box-shadow:', light_theme_section)


if __name__ == '__main__':
    unittest.main()
