"""
Pytest configuration and fixtures.
"""
import sys
from pathlib import Path
from tqdm import tqdm

# Disable tqdm monitor thread globally to prevent crashes on Windows during tests
tqdm.monitor_interval = 0

# Add the parent directory to sys.path so we can import snap_memories
tests_dir = Path(__file__).parent
project_root = tests_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def pytest_sessionfinish(session, exitstatus):
    """Generate performance report after all tests complete."""
    # Import here to avoid circular imports
    try:
        from test_combining_performance import _perf_results
        
        if _perf_results.results:
            import json
            from datetime import datetime
            
            # Generate report
            report = _perf_results.generate_report()
            
            # Save to file
            report_file = Path("tests") / "performance_report.txt"
            report_file.parent.mkdir(exist_ok=True)
            report_file.write_text(report, encoding='utf-8')
            
            # Save JSON
            json_file = Path("tests") / "performance_report.json"
            _perf_results.save_json(json_file)
            
            # Print to console
            print("\n" + report)
            print(f"\nReport saved to: {report_file}")
            print(f"JSON saved to: {json_file}")
    except ImportError:
        # If the performance test module isn't imported, skip report generation
        pass
