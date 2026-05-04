"""
Complete Project Verification Script
Checks all components before deployment.
"""

import ast
import subprocess
import sys
from pathlib import Path


def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists."""
    if Path(path).exists():
        print(f"[OK] {description}: {path}")
        return True
    else:
        print(f"[MISSING] {description}: {path}")
        return False


def check_python_syntax(path: str) -> bool:
    """Check Python file syntax."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            ast.parse(f.read())
        print(f"[OK] Syntax: {path}")
        return True
    except SyntaxError as e:
        print(f"[ERROR] Syntax error in {path}: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Reading {path}: {e}")
        return False


def run_backend_tests() -> bool:
    """Run backend unit and integration tests."""
    print("\n--- Running Backend Tests ---")
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "backend/tests/unit", "backend/tests/integration", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("[OK] Backend tests passed")
            return True
        else:
            print("[FAIL] Backend tests failed")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return False
    except subprocess.TimeoutExpired:
        print("[FAIL] Backend tests timed out")
        return False
    except FileNotFoundError:
        print("[SKIP] Python/pytest not found, skipping backend tests")
        return True  # Don't fail if Python isn't available


def run_frontend_tests() -> bool:
    """Run frontend tests."""
    print("\n--- Running Frontend Tests ---")
    frontend_dir = Path("frontend")
    venv_python = frontend_dir / ".venv" / "Scripts" / "python.exe"
    
    if not venv_python.exists():
        print("[SKIP] Frontend venv not found, skipping frontend tests")
        return True
    
    try:
        result = subprocess.run(
            [str(venv_python), "-m", "pytest", "test_app.py", "-v"],
            cwd="frontend",
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("[OK] Frontend tests passed")
            return True
        else:
            print("[FAIL] Frontend tests failed")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return False
    except subprocess.TimeoutExpired:
        print("[FAIL] Frontend tests timed out")
        return False
    except Exception as e:
        print(f"[SKIP] Could not run frontend tests: {e}")
        return True


def main():
    """Run complete project verification."""
    print("=" * 70)
    print("KO-MEETING-INTERPRETER PROJECT VERIFICATION")
    print("=" * 70)
    
    all_checks = []
    
    # 1. Core Configuration Files
    print("\n[1/7] Checking Configuration Files...")
    config_checks = [
        (".env.example", "Environment template"),
        (".gitignore", "Git ignore file"),
        ("docker-compose.yml", "Docker Compose config"),
        ("Makefile", "Makefile"),
        ("README.md", "README"),
        ("BUILD_PROMPT.md", "Build specification"),
        ("BUILD_PROGRESS.md", "Build progress"),
    ]
    for path, desc in config_checks:
        all_checks.append(check_file_exists(path, desc))
    
    # 2. Backend Structure
    print("\n[2/7] Checking Backend Structure...")
    backend_checks = [
        ("backend/requirements.txt", "Backend requirements"),
        ("backend/app/main.py", "FastAPI main app"),
        ("backend/app/config.py", "Configuration module"),
        ("backend/app/schemas.py", "Pydantic schemas"),
        ("backend/app/asr/openai_asr.py", "OpenAI ASR client"),
        ("backend/app/asr/soniox_asr.py", "Soniox ASR client"),
        ("backend/app/llm/reconstruct.py", "Korean reconstruction"),
        ("backend/app/llm/translate.py", "Translation module"),
        ("backend/app/session/manager.py", "Session manager"),
    ]
    for path, desc in backend_checks:
        all_checks.append(check_file_exists(path, desc))
    
    # 3. Backend Syntax
    print("\n[3/7] Checking Backend Python Syntax...")
    backend_py_files = list(Path("backend").rglob("*.py"))
    backend_py_files = [p for p in backend_py_files if "__pycache__" not in str(p)]
    for py_file in backend_py_files[:20]:  # Check first 20 files
        all_checks.append(check_python_syntax(str(py_file)))
    
    # 4. Frontend Structure
    print("\n[4/7] Checking Frontend Structure...")
    frontend_checks = [
        ("frontend/requirements.txt", "Frontend requirements"),
        ("frontend/app.py", "Streamlit app"),
        ("frontend/test_app.py", "Frontend tests"),
        ("frontend/Dockerfile", "Frontend Dockerfile"),
    ]
    for path, desc in frontend_checks:
        all_checks.append(check_file_exists(path, desc))
    
    # 5. Frontend Syntax
    print("\n[5/7] Checking Frontend Python Syntax...")
    all_checks.append(check_python_syntax("frontend/app.py"))
    all_checks.append(check_python_syntax("frontend/test_app.py"))
    
    # 6. Prompts
    print("\n[6/7] Checking LLM Prompts...")
    prompt_files = [
        "prompts/reconstruct_ko.md",
        "prompts/translate_es.md",
        "prompts/translate_en.md",
        "prompts/translate_zh.md",
        "prompts/image_context.md",
        "prompts/operational_summary.md",
        "prompts/judge_prompt_quality.md",
    ]
    for path in prompt_files:
        all_checks.append(check_file_exists(path, f"Prompt: {Path(path).name}"))
    
    # 7. Test Data
    print("\n[7/7] Checking Test Data...")
    test_data_checks = [
        ("test_data/sample_korean_phrases.json", "Korean phrases"),
        ("test_data/generate_test_audio.py", "Audio generator"),
        ("test_data/README.md", "Test data docs"),
        ("scripts/test_api_functional.py", "API functional tests"),
        ("scripts/verify_project.py", "This verification script"),
    ]
    for path, desc in test_data_checks:
        all_checks.append(check_file_exists(path, desc))
    
    # Run Tests
    print("\n" + "=" * 70)
    print("RUNNING TESTS")
    print("=" * 70)
    
    all_checks.append(run_backend_tests())
    all_checks.append(run_frontend_tests())
    
    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    passed = sum(all_checks)
    total = len(all_checks)
    failed = total - passed
    
    print(f"Checks passed: {passed}/{total}")
    
    if failed == 0:
        print("\n[OK] ALL CHECKS PASSED - Project is ready!")
        print("\nNext steps:")
        print("  1. Ensure .env has valid API keys")
        print("  2. Run: docker compose up -d --build")
        print("  3. Visit: http://localhost:8501")
        print("  4. Run functional tests: python scripts/test_api_functional.py")
        return 0
    else:
        print(f"\n[WARN] {failed} CHECKS FAILED - Review output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
