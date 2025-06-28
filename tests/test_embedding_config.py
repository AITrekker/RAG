"""
Pytest-based tests for embedding model configuration and performance.
"""

import pytest
from unittest.mock import patch
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backend.config.settings import (
    get_embedding_model_config, 
    validate_rtx_5070_compatibility,
)
from src.backend.core.embeddings import get_embedding_service, EmbeddingService

# --- Fixtures ---

@pytest.fixture(scope="module")
def default_embedding_service():
    """Provides a default embedding service instance for the module."""
    return get_embedding_service(force_reload=True)

# Helper to check for CUDA and specific GPU
rtx_5070_compatibility = validate_rtx_5070_compatibility()
has_rtx_5070 = rtx_5070_compatibility['rtx_5070_detected']
cuda_available = rtx_5070_compatibility['cuda_available']

# --- Test Classes ---

class TestEmbeddingConfiguration:
    """Tests for the embedding model configuration system."""

    def test_configuration_loading(self):
        """Test that the embedding model configuration can be loaded."""
        config = get_embedding_model_config()
        assert isinstance(config, dict)
        assert "model_name" in config
        assert "device" in config
        assert "batch_size" in config

class TestEmbeddingServiceIntegration:
    """Tests the integration of configurations with the EmbeddingService."""

    def test_service_initialization_with_defaults(self, default_embedding_service):
        """Test that the service initializes with default settings."""
        service = default_embedding_service
        assert isinstance(service, EmbeddingService)
        assert service.model_name is not None
        assert service.device is not None

    def test_loading_different_models(self):
        """Test that a model can be loaded by the service."""
        try:
            config = get_embedding_model_config()
            model_name = config.get("model_name")
            assert model_name is not None, "Model name should be in the config."
            
            service = get_embedding_service(model_name=model_name, force_reload=True)
            assert service.model_name == model_name
            # A simple check to ensure the model is functional
            embedding = service.encode_single_text("test")
            assert embedding is not None
        except Exception as e:
            pytest.fail(f"Failed to load model {model_name}: {e}")

@pytest.mark.skipif(not cuda_available, reason="CUDA is not available for this test.")
class TestPerformanceBenchmarks:
    """Performance benchmarks, requires a CUDA-enabled GPU."""

    @pytest.mark.skipif(not has_rtx_5070, reason="Requires NVIDIA RTX 5070 for this specific benchmark.")
    def test_rtx_5070_performance(self, default_embedding_service):
        """Benchmark performance against the defined target for RTX 5070."""
        service = default_embedding_service
        texts = ["This is a test sentence for benchmarking."] * 32
        
        import time
        start_time = time.time()
        service.encode_batch_texts(texts)
        duration = time.time() - start_time
        
        texts_per_sec = len(texts) / duration
        
        # We expect the performance to be at least 70% of the target.
        # This allows for some variance in system conditions.
        assert texts_per_sec >= (service.target_performance * 0.7), \
            f"Performance ({texts_per_sec:.2f} txt/s) is below 70% of target ({service.target_performance} txt/s)"

    def test_general_gpu_performance(self, default_embedding_service):
        """A general performance test for any available GPU."""
        service = default_embedding_service
        if service.device == "cpu":
            pytest.skip("Skipping GPU performance test on CPU.")

        texts = ["This is a test sentence."] * 16
        
        import time
        start_time = time.time()
        service.encode_batch_texts(texts)
        duration = time.time() - start_time

        assert duration < 5, "Batch processing on GPU should be reasonably fast." 