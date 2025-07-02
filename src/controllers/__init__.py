"""
Controllers Module - UI-Service Decoupling Layer

This module provides Controller classes that act as intermediaries between
UI components and business logic services, ensuring complete separation of concerns.

Architecture Principles:
- Controllers handle UI events and coordinate service calls
- UI components remain pure presentation layer
- Services remain pure business logic layer
- Controllers manage dependency injection and state synchronization
"""

from .chat_controller import ChatController
from .annotation_controller import AnnotationController
from .pdf_controller import PDFController
from .application_controller import ApplicationController

__all__ = [
    'ChatController',
    'AnnotationController', 
    'PDFController',
    'ApplicationController'
] 