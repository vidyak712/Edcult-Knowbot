"""
Application Insights Logger Utility
Provides structured logging to Azure Application Insights
Follows 2024 best practices for Python logging
"""

import logging
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from azure.monitor.opentelemetry import configure_azure_monitor

load_dotenv()

# Configure Azure Monitor with OpenTelemetry
APPINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATION_INSIGHTS_CONNECTION_STRING")

if APPINSIGHTS_CONNECTION_STRING:
    configure_azure_monitor(connection_string=APPINSIGHTS_CONNECTION_STRING)

# Get logger
logger = logging.getLogger(__name__)


class AppInsightsLogger:
    """
    Structured logger for Application Insights
    Provides info, warning, and error logging with custom properties
    """
    
    def __init__(self, component_name: str = "KnowBot"):
        """
        Initialize the logger
        
        Args:
            component_name: Name of the component/module using this logger
        """
        self.component_name = component_name
        self.logger = logging.getLogger(component_name)
        
        # Configure logging
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def info(
        self,
        message: str,
        properties: Optional[Dict[str, Any]] = None,
        measurements: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Log info message with optional custom properties
        
        Args:
            message: Log message
            properties: Custom properties/dimensions dict
            measurements: Custom metrics dict
        """
        self._log("INFO", message, properties, measurements)
    
    def warning(
        self,
        message: str,
        properties: Optional[Dict[str, Any]] = None,
        measurements: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Log warning message with optional custom properties
        
        Args:
            message: Log message
            properties: Custom properties/dimensions dict
            measurements: Custom metrics dict
        """
        self._log("WARNING", message, properties, measurements)
    
    def error(
        self,
        message: str,
        exception: Optional[Exception] = None,
        properties: Optional[Dict[str, Any]] = None,
        measurements: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Log error message with optional exception and custom properties
        
        Args:
            message: Log message
            exception: Exception object (optional)
            properties: Custom properties/dimensions dict
            measurements: Custom metrics dict
        """
        if exception:
            self.logger.error(
                f"{message} - {str(exception)}",
                exc_info=True,
                extra=self._build_extra(properties, measurements)
            )
        else:
            self._log("ERROR", message, properties, measurements)
    
    def _log(
        self,
        level: str,
        message: str,
        properties: Optional[Dict[str, Any]] = None,
        measurements: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Internal method to handle logging
        """
        extra = self._build_extra(properties, measurements)
        
        if level == "INFO":
            self.logger.info(message, extra=extra)
        elif level == "WARNING":
            self.logger.warning(message, extra=extra)
        elif level == "ERROR":
            self.logger.error(message, extra=extra)
    
    def _build_extra(
        self,
        properties: Optional[Dict[str, Any]] = None,
        measurements: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Build extra dict for logging context
        """
        extra = {
            "component": self.component_name,
            "custom_dimensions": properties or {},
            "custom_measurements": measurements or {}
        }
        return extra


# Create module-level logger instance
_module_logger = AppInsightsLogger("KnowBot")


def get_logger(component_name: str = "KnowBot") -> AppInsightsLogger:
    """
    Get an Application Insights logger instance
    
    Args:
        component_name: Name of the component using this logger
    
    Returns:
        AppInsightsLogger instance
    """
    return AppInsightsLogger(component_name)


def log_info(
    message: str,
    properties: Optional[Dict[str, Any]] = None,
    measurements: Optional[Dict[str, float]] = None
) -> None:
    """Log info message"""
    _module_logger.info(message, properties, measurements)


def log_warning(
    message: str,
    properties: Optional[Dict[str, Any]] = None,
    measurements: Optional[Dict[str, float]] = None
) -> None:
    """Log warning message"""
    _module_logger.warning(message, properties, measurements)


def log_error(
    message: str,
    exception: Optional[Exception] = None,
    properties: Optional[Dict[str, Any]] = None,
    measurements: Optional[Dict[str, float]] = None
) -> None:
    """Log error message"""
    _module_logger.error(message, exception, properties, measurements)
