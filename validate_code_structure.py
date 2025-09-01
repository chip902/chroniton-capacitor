#!/usr/bin/env python3
"""
Phase 5 Code Structure Validation

This script validates that all Phase 5 components exist and have the expected structure.
It doesn't require external dependencies, just checks file structure and basic imports.
"""

import os
import sys
import ast
from pathlib import Path

def check_file_exists(filepath):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"  ✓ {filepath}")
        return True
    else:
        print(f"  ✗ {filepath} - MISSING")
        return False

def check_class_exists(filepath, class_name):
    """Check if a class exists in a Python file"""
    if not os.path.exists(filepath):
        return False
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return True
        return False
    except Exception as e:
        print(f"    Error parsing {filepath}: {e}")
        return False

def check_function_exists(filepath, function_name):
    """Check if a function exists in a Python file"""
    if not os.path.exists(filepath):
        return False
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                return True
            elif isinstance(node, ast.AsyncFunctionDef) and node.name == function_name:
                return True
        return False
    except Exception as e:
        print(f"    Error parsing {filepath}: {e}")
        return False

def validate_sync_engine():
    """Validate sync engine implementation"""
    print("\n🔄 Validating Sync Engine Implementation...")
    
    filepath = "src/sync/sync_engine.py"
    results = []
    
    # Check file exists
    results.append(check_file_exists(filepath))
    
    if os.path.exists(filepath):
        # Check key classes exist
        classes = [
            "BidirectionalSyncEngine",
            "SyncProgress",
            "EventDeduplicator",
            "BatchProcessor"
        ]
        
        for class_name in classes:
            if check_class_exists(filepath, class_name):
                print(f"    ✓ Class {class_name} exists")
                results.append(True)
            else:
                print(f"    ✗ Class {class_name} missing")
                results.append(False)
        
        # Check key methods exist
        methods = [
            "sync_bidirectional",
            "deduplicate_events",
            "process_batch"
        ]
        
        for method_name in methods:
            if check_function_exists(filepath, method_name):
                print(f"    ✓ Method {method_name} exists")
                results.append(True)
            else:
                print(f"    ✗ Method {method_name} missing")
                results.append(False)
    
    return all(results)

def validate_conflict_resolution():
    """Validate conflict resolution implementation"""
    print("\n⚡ Validating Conflict Resolution Implementation...")
    
    filepath = "src/sync/conflict_resolver.py"
    results = []
    
    # Check file exists
    results.append(check_file_exists(filepath))
    
    if os.path.exists(filepath):
        # Check key classes exist
        classes = [
            "ConflictManager",
            "ConflictDetector", 
            "ConflictResolver",
            "Conflict",
            "ConflictStrategy"
        ]
        
        for class_name in classes:
            if check_class_exists(filepath, class_name):
                print(f"    ✓ Class {class_name} exists")
                results.append(True)
            else:
                print(f"    ✗ Class {class_name} missing")
                results.append(False)
        
        # Check key methods exist
        methods = [
            "detect_conflicts",
            "resolve_conflict",
            "apply_resolution"
        ]
        
        for method_name in methods:
            if check_function_exists(filepath, method_name):
                print(f"    ✓ Method {method_name} exists")
                results.append(True)
            else:
                print(f"    ✗ Method {method_name} missing")
                results.append(False)
    
    return all(results)

def validate_token_management():
    """Validate token management implementation"""
    print("\n🔑 Validating Token Management Implementation...")
    
    filepath = "src/sync/token_manager.py"
    results = []
    
    # Check file exists
    results.append(check_file_exists(filepath))
    
    if os.path.exists(filepath):
        # Check key classes exist
        classes = [
            "TokenManager",
            "TokenValidator",
            "SyncToken"
        ]
        
        for class_name in classes:
            if check_class_exists(filepath, class_name):
                print(f"    ✓ Class {class_name} exists")
                results.append(True)
            else:
                print(f"    ✗ Class {class_name} missing")
                results.append(False)
        
        # Check key methods exist
        methods = [
            "get_sync_token",
            "store_sync_token",
            "validate_token",
            "refresh_token"
        ]
        
        for method_name in methods:
            if check_function_exists(filepath, method_name):
                print(f"    ✓ Method {method_name} exists")
                results.append(True)
            else:
                print(f"    ✗ Method {method_name} missing")
                results.append(False)
    
    return all(results)

def validate_realtime_sync():
    """Validate real-time sync implementation"""
    print("\n⚡ Validating Real-time Sync Implementation...")
    
    filepath = "src/sync/realtime_sync.py"
    results = []
    
    # Check file exists
    results.append(check_file_exists(filepath))
    
    if os.path.exists(filepath):
        # Check key classes exist
        classes = [
            "RealtimeSyncEngine",
            "WebhookReceiver",
            "PollingScheduler",
            "WebSocketManager"
        ]
        
        for class_name in classes:
            if check_class_exists(filepath, class_name):
                print(f"    ✓ Class {class_name} exists")
                results.append(True)
            else:
                print(f"    ✗ Class {class_name} missing")
                results.append(False)
        
        # Check key methods exist
        methods = [
            "process_webhook",
            "start_polling",
            "broadcast_update"
        ]
        
        for method_name in methods:
            if check_function_exists(filepath, method_name):
                print(f"    ✓ Method {method_name} exists")
                results.append(True)
            else:
                print(f"    ✗ Method {method_name} missing")
                results.append(False)
    
    return all(results)

def validate_controller_integration():
    """Validate controller integration"""
    print("\n🎛️ Validating Controller Integration...")
    
    filepath = "src/sync/controller.py"
    results = []
    
    # Check file exists
    results.append(check_file_exists(filepath))
    
    if os.path.exists(filepath):
        # Check BackgroundTasks is imported
        with open(filepath, 'r') as f:
            content = f.read()
        
        if 'BackgroundTasks' in content:
            print("    ✓ BackgroundTasks imported")
            results.append(True)
        else:
            print("    ✗ BackgroundTasks not imported")
            results.append(False)
        
        # Check enhanced sync components are imported
        enhanced_components = [
            "BidirectionalSyncEngine",
            "ConflictManager", 
            "TokenManager",
            "RealtimeSyncEngine"
        ]
        
        for component in enhanced_components:
            if component in content:
                print(f"    ✓ {component} imported")
                results.append(True)
            else:
                print(f"    ✗ {component} not imported")
                results.append(False)
        
        # Check method signatures include background_tasks parameter
        methods_with_background_tasks = [
            "sync_all_calendars",
            "sync_single_source", 
            "sync_agent_events"
        ]
        
        for method_name in methods_with_background_tasks:
            if f"{method_name}(" in content and "background_tasks" in content:
                print(f"    ✓ Method {method_name} uses BackgroundTasks")
                results.append(True)
            else:
                print(f"    ✗ Method {method_name} missing BackgroundTasks integration")
                results.append(False)
    
    return all(results)

def validate_api_integration():
    """Validate API router integration"""
    print("\n🌐 Validating API Integration...")
    
    filepath = "src/api/sync_router.py"
    results = []
    
    # Check file exists
    results.append(check_file_exists(filepath))
    
    if os.path.exists(filepath):
        # Check BackgroundTasks is imported
        with open(filepath, 'r') as f:
            content = f.read()
        
        if 'BackgroundTasks' in content:
            print("    ✓ BackgroundTasks imported in router")
            results.append(True)
        else:
            print("    ✗ BackgroundTasks not imported in router")
            results.append(False)
        
        # Check endpoints use BackgroundTasks parameter
        endpoints_with_background_tasks = [
            "sync_all_calendars",
            "sync_single_source",
            "import_events",
            "test_end_to_end_sync"
        ]
        
        for endpoint in endpoints_with_background_tasks:
            if f"def {endpoint}(" in content and "background_tasks: BackgroundTasks" in content:
                print(f"    ✓ Endpoint {endpoint} uses BackgroundTasks")
                results.append(True)
            else:
                print(f"    ✗ Endpoint {endpoint} missing BackgroundTasks parameter")
                results.append(False)
    
    return all(results)

def validate_test_files():
    """Validate test files exist"""
    print("\n🧪 Validating Test Files...")
    
    test_files = [
        "test_bidirectional_sync.py",
        "validate_phase5_implementation.py"
    ]
    
    results = []
    
    for test_file in test_files:
        results.append(check_file_exists(test_file))
    
    return all(results)

def main():
    """Run all validations"""
    print("📋 Phase 5 Code Structure Validation")
    print("=" * 50)
    
    validation_functions = [
        validate_sync_engine,
        validate_conflict_resolution,
        validate_token_management, 
        validate_realtime_sync,
        validate_controller_integration,
        validate_api_integration,
        validate_test_files
    ]
    
    results = []
    
    for validation_func in validation_functions:
        try:
            result = validation_func()
            results.append(result)
        except Exception as e:
            print(f"Validation error in {validation_func.__name__}: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    validation_names = [
        "Sync Engine Implementation",
        "Conflict Resolution Implementation", 
        "Token Management Implementation",
        "Real-time Sync Implementation",
        "Controller Integration",
        "API Integration", 
        "Test Files"
    ]
    
    for i, (name, result) in enumerate(zip(validation_names, results)):
        status = "✓ PASS" if result else "✗ FAIL" 
        print(f"  {status} {name}")
    
    print(f"\nOverall Result: {passed}/{total} validations passed")
    
    if passed == total:
        print("🎉 ALL VALIDATIONS PASSED - Phase 5 implementation structure is complete!")
        print("\n💡 Next steps:")
        print("  1. Install dependencies: pip install fastapi uvicorn")
        print("  2. Run validation script: python validate_phase5_implementation.py")
        print("  3. Run integration tests: pytest test_bidirectional_sync.py")
        print("  4. Start the API server: python -m src.main")
        return True
    else:
        print("⚠️  Some validations failed - check implementation files")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)