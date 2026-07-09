#!/usr/bin/env python3
"""
Integration test for the Scanner service.
Verifies all components work together.
"""

import asyncio
import sys
from pathlib import Path

# Add app to path
app_path = Path(__file__).parent
sys.path.insert(0, str(app_path))


async def test_imports():
    """Test that all scanner modules can be imported."""
    print("Testing imports...")
    try:
        from app.services.scanner.base import BaseScanner, ScanResult
        from app.services.scanner.config import get_config, get_all_keywords
        from app.services.scanner.news_scanner import NewsScanner
        from app.services.scanner.web_scanner import WebScanner
        from app.services.scanner.x_scanner import XScanner
        from app.services.scanner.github_scanner import GitHubScanner
        from app.services.scanner.orchestrator import ScannerOrchestrator
        from app.api import scanner as scanner_api
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


async def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    try:
        from app.services.scanner.config import get_config, get_all_keywords

        config = get_config()
        assert config.keywords, "Keywords not loaded"
        assert config.sources_enabled, "Sources not configured"

        keywords = get_all_keywords()
        assert len(keywords) > 0, "No keywords found"

        print(f"✓ Configuration loaded ({len(keywords)} keywords)")
        print(f"  Enabled sources: {list(config.sources_enabled.keys())}")
        return True
    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False


async def test_scan_result():
    """Test ScanResult structure."""
    print("\nTesting ScanResult...")
    try:
        from app.services.scanner.base import ScanResult
        from datetime import datetime

        result = ScanResult(
            source="test",
            title="Test Title",
            content="Test content",
            url="https://example.com",
            timestamp=datetime.utcnow(),
            relevance_score=0.75,
            tags=["test"],
        )

        result_dict = result.to_dict()
        assert result_dict["source"] == "test"
        assert result_dict["relevance_score"] == 0.75
        assert "timestamp" in result_dict

        print(f"✓ ScanResult structure valid")
        print(f"  {result}")
        return True
    except Exception as e:
        print(f"✗ ScanResult test failed: {e}")
        return False


async def test_orchestrator():
    """Test orchestrator initialization."""
    print("\nTesting orchestrator...")
    try:
        from app.services.scanner.orchestrator import ScannerOrchestrator

        orchestrator = ScannerOrchestrator()
        assert orchestrator.scanners, "No scanners initialized"
        assert len(orchestrator.scanners) > 0, "No scanners configured"

        status = await orchestrator.get_status()
        assert "running" in status
        assert "enabled_sources" in status

        print(f"✓ Orchestrator initialized")
        print(f"  Scanners: {list(orchestrator.scanners.keys())}")
        print(f"  Running: {status['running']}")
        return True
    except Exception as e:
        print(f"✗ Orchestrator test failed: {e}")
        return False


async def test_memory_integration():
    """Test integration with memory service."""
    print("\nTesting memory integration...")
    try:
        from app.services import memory

        # Store test intelligence
        mem_id = memory.store_memory(
            content="Test intelligence",
            metadata={
                "source": "test",
                "url": "https://example.com",
                "relevance_score": 0.8,
                "tags": ["test"],
            },
            collection_name="intelligence",
        )

        assert mem_id, "Failed to store memory"

        # Recall it
        results = memory.recall_memories(
            query="test",
            n_results=5,
            collection_name="intelligence",
        )

        assert len(results) > 0, "Failed to recall memory"
        assert results[0]["content"] == "Test intelligence"

        # Cleanup
        memory.delete_memory(mem_id, "intelligence")

        print(f"✓ Memory integration working")
        print(f"  Stored and recalled intelligence successfully")
        return True
    except Exception as e:
        print(f"✗ Memory test failed: {e}")
        return False


async def test_api_models():
    """Test FastAPI models."""
    print("\nTesting API models...")
    try:
        from app.api.scanner import (
            ScannerStatus,
            ScannerConfig,
            BriefingResponse,
        )

        # Test ScannerStatus
        status = ScannerStatus(
            running=False,
            last_full_scan=None,
            scan_count=0,
            error_count=0,
            last_scan_times={},
            enabled_sources=["news"],
            memory_stats={"collection": "intelligence", "total_memories": 0},
        )
        assert status.running is False

        # Test ScannerConfig
        config = ScannerConfig(
            keywords={"test": ["keyword"]},
            sources_enabled={"news": True},
            scan_intervals={"news": 60},
            relevance_threshold=0.3,
            max_results_per_scan=10,
        )
        assert config.relevance_threshold == 0.3

        # Test BriefingResponse
        briefing = BriefingResponse(
            content="# Test Briefing",
            generated_at="2026-02-26T00:00:00",
        )
        assert "Test Briefing" in briefing.content

        print(f"✓ API models valid")
        return True
    except Exception as e:
        print(f"✗ API model test failed: {e}")
        return False


async def test_scanner_initialization():
    """Test individual scanner initialization."""
    print("\nTesting scanner initialization...")
    try:
        from app.services.scanner.news_scanner import NewsScanner
        from app.services.scanner.web_scanner import WebScanner
        from app.services.scanner.x_scanner import XScanner
        from app.services.scanner.github_scanner import GitHubScanner

        scanners = [
            ("NewsScanner", NewsScanner()),
            ("WebScanner", WebScanner()),
            ("XScanner", XScanner()),
            ("GitHubScanner", GitHubScanner()),
        ]

        for name, scanner in scanners:
            assert scanner.name, f"{name} has no name"
            assert hasattr(scanner, "scan"), f"{name} missing scan method"
            assert hasattr(
                scanner, "parse_results"
            ), f"{name} missing parse_results"
            assert hasattr(
                scanner, "filter_relevant"
            ), f"{name} missing filter_relevant"

        print(f"✓ All scanners properly initialized")
        print(f"  Scanners: {[name for name, _ in scanners]}")

        # Cleanup
        for _, scanner in scanners:
            await scanner.close()

        return True
    except Exception as e:
        print(f"✗ Scanner initialization test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("CIPHER SCANNER SERVICE - INTEGRATION TEST")
    print("=" * 60)

    tests = [
        test_imports,
        test_config,
        test_scan_result,
        test_orchestrator,
        test_memory_integration,
        test_api_models,
        test_scanner_initialization,
    ]

    results = []
    for test_func in tests:
        result = await test_func()
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 60)

    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
