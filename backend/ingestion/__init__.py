"""
Ingestion module for parsing infrastructure data files
Supports XML (OSM) file format for power and water infrastructure
"""

from .xml_parser import OSMParser

__all__ = [
    "OSMParser"
]