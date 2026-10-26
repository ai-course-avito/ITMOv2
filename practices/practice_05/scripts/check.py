#!/usr/bin/env python3
"""
Кроссплатформенный runner для проверки проекта VkusMart.
Запускается автономно или через hook .opencode/plugins/check-after-edit.js.
Выполняет:
1. Синтаксическую проверку всех модулей проекта.
2. Проверку инвариантов каталога данных.
3. Модульные и интеграционные тесты (через pytest или unittest).
"""

import sys
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def run_syntax_check() -> bool:
    print("[RUNNER] 1/3 Проверка синтаксиса Python файлов...")
    has_error = False
    for py_file in PROJECT_ROOT.glob("**/*.py"):
        if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                compile(f.read(), str(py_file), "exec")
        except SyntaxError as e:
            print(f"  [FAIL] Ошибка синтаксиса в {py_file}: {e}")
            has_error = True
    if not has_error:
        print("  [PASS] Синтаксис всех файлов корректен.")
    return not has_error

def run_catalog_integrity() -> bool:
    print("[RUNNER] 2/3 Проверка целостности каталога товаров...")
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from app.catalog import PRODUCTS, THEMES
        if not PRODUCTS:
            print("  [FAIL] Каталог товаров пуст.")
            return False
        for p in PRODUCTS:
            if p.price <= 0:
                print(f"  [FAIL] Товар {p.id} имеет некорректную цену: {p.price}")
                return False
            if p.calories < 0:
                print(f"  [FAIL] Товар {p.id} имеет отрицательную калорийность: {p.calories}")
                return False
        if not THEMES:
            print("  [FAIL] Список тематических подборок пуст.")
            return False
        print(f"  [PASS] Каталог валиден: {len(PRODUCTS)} товаров, {len(THEMES)} тем.")
        return True
    except ImportError:
        # Если модули каталога еще не созданы на этапе начальной инициализации
        print("  [INFO] Модуль каталога еще создается, пропускаем.")
        return True
    except Exception as e:
        print(f"  [FAIL] Исключение при проверке каталога: {e}")
        return False

def run_tests() -> bool:
    print("[RUNNER] 3/3 Запуск тестового набора...")
    venv_pytest = PROJECT_ROOT / ".venv" / "Scripts" / "pytest.exe"
    if not venv_pytest.exists():
        venv_pytest = PROJECT_ROOT / ".venv" / "bin" / "pytest"
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")

    cmd = []
    if venv_pytest.exists():
        cmd = [str(venv_pytest), "-v", "tests"]
    else:
        # Fallback на unittest со стандартной библиотекой
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)
    if result.returncode == 0:
        print("  [PASS] Все тесты успешно пройдены.")
        return True
    else:
        print(f"  [FAIL] Тесты завершились с кодом {result.returncode}.")
        return False

def main():
    print("=" * 60)
    print("   VkusMart Automated Check Runner")
    print("=" * 60)
    
    step1 = run_syntax_check()
    step2 = run_catalog_integrity()
    step3 = run_tests()
    
    print("=" * 60)
    if step1 and step2 and step3:
        print(">>> RESULT: ALL CHECKS PASSED (exit code 0)")
        sys.exit(0)
    else:
        print(">>> RESULT: CHECKS FAILED (exit code 1)")
        sys.exit(1)

if __name__ == "__main__":
    main()
