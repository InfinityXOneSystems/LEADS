"""ML-powered scoring service."""
import json
import os
from typing import Dict, Any, Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_WEIGHTS = {
    "legitimacy": 0.20,
    "relevance": 0.25,
    "opportunity": 0.15,
    "activity": 0.15,
    "accessibility": 0.15,
    "engagement": 0.10,
}


class ScoringService:
    """Manages scoring weights and model configuration."""

    def __init__(self, weights_path: Optional[str] = None):
        self.weights = self._load_weights(weights_path)

    def _load_weights(self, weights_path: Optional[str]) -> Dict[str, float]:
        """Load scoring weights from JSON file."""
        if weights_path and os.path.exists(weights_path):
            try:
                with open(weights_path) as f:
                    data = json.load(f)
                    return data.get("weights", DEFAULT_WEIGHTS)
            except Exception as e:
                logger.warning(f"Failed to load weights from {weights_path}: {e}")
        return DEFAULT_WEIGHTS

    def get_weights(self) -> Dict[str, float]:
        """Get current scoring weights."""
        return self.weights.copy()

    def update_weights(self, new_weights: Dict[str, float]) -> bool:
        """Update scoring weights (must sum to 1.0)."""
        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.001:
            logger.error(f"Weights must sum to 1.0, got {total}")
            return False
        self.weights = new_weights
        return True
