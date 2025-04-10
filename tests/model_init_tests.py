import os
import sys
import time
import torch
import psutil
import logging
import traceback
from typing import Dict, Any
from transformers import AutoModelForCausalLM, AutoTokenizer

# Add parent directory to path to import server components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import (
    MODEL_PATH,
    log_gpu_memory,
    check_system_resources,
    clear_gpu_memory
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_current_implementation() -> Dict[str, Any]:
    """Test current implementation with both manual and auto initialization"""
    metrics = {}
    try:
        # Clear existing models and memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        
        # Manual GPU setup
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            logger.info("GPU memory cleared")
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        logger.info("Tokenizer loaded successfully")
        
        # Load model with both manual and auto settings
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            device_map="auto",
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        
        # Collect metrics
        metrics["memory_usage"] = torch.cuda.memory_allocated() / (1024**3)  # GB
        metrics["gpu_utilization"] = torch.cuda.utilization() if hasattr(torch.cuda, 'utilization') else 0
        metrics["success_rate"] = 100
        
        return metrics
        
    except Exception as e:
        logger.error(f"Current implementation test failed: {str(e)}")
        metrics["success_rate"] = 0
        metrics["error_type"] = type(e).__name__
        return metrics

def setup_auto_only() -> Dict[str, Any]:
    """Test using only AutoModelForCausalLM's device_map='auto'"""
    metrics = {}
    try:
        # Clear GPU memory
        clear_gpu_memory()
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        
        # Load model with auto settings only
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            device_map="auto",
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        
        # Collect metrics
        metrics["memory_usage"] = torch.cuda.memory_allocated() / (1024**3)  # GB
        metrics["gpu_utilization"] = torch.cuda.utilization() if hasattr(torch.cuda, 'utilization') else 0
        metrics["success_rate"] = 100
        
        return metrics
        
    except Exception as e:
        logger.error(f"Auto-only test failed: {str(e)}")
        metrics["success_rate"] = 0
        metrics["error_type"] = type(e).__name__
        return metrics

def setup_manual_only() -> Dict[str, Any]:
    """Test using only manual GPU initialization"""
    metrics = {}
    try:
        # Clear GPU memory
        clear_gpu_memory()
        
        # Manual GPU setup
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        
        # Load model with manual settings only
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        
        # Move model to GPU manually
        if torch.cuda.is_available():
            model = model.cuda()
        
        # Collect metrics
        metrics["memory_usage"] = torch.cuda.memory_allocated() / (1024**3)  # GB
        metrics["gpu_utilization"] = torch.cuda.utilization() if hasattr(torch.cuda, 'utilization') else 0
        metrics["success_rate"] = 100
        
        return metrics
        
    except Exception as e:
        logger.error(f"Manual-only test failed: {str(e)}")
        metrics["success_rate"] = 0
        metrics["error_type"] = type(e).__name__
        return metrics

def setup_low_memory():
    """Test initialization with progressively constrained memory settings"""
    metrics = {
        'init_time': 0,
        'memory_usage': 0,
        'gpu_utilization': 0,
        'success_rate': 0,
        'errors': []
    }
    
    # Start with full memory allocation
    memory_factors = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
    successful_init = False
    
    for factor in memory_factors:
        try:
            start_time = time.time()
            
            # Calculate memory settings based on factor
            max_memory = int(14 * 1024 * 1024 * 1024 * factor)  # Start with 14GB and reduce
            device_map = "auto"
            torch_dtype = torch.float16
            
            # Initialize model with current memory settings
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_PATH,
                device_map=device_map,
                torch_dtype=torch_dtype,
                max_memory=max_memory,
                trust_remote_code=True
            )
            
            # Test model with a small inference
            test_input = "Hello, how are you?"
            inputs = tokenizer(test_input, return_tensors="pt").to(model.device)
            outputs = model.generate(**inputs, max_length=50)
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            end_time = time.time()
            metrics['init_time'] = end_time - start_time
            metrics['memory_usage'] = log_gpu_memory()
            metrics['gpu_utilization'] = get_gpu_utilization()
            metrics['success_rate'] = 1.0
            successful_init = True
            
            print(f"\nSuccessfully initialized with {factor*100}% memory allocation")
            print(f"Memory used: {metrics['memory_usage'] / (1024**3):.2f} GB")
            print(f"Initialization time: {metrics['init_time']:.2f} seconds")
            
            # If successful, we've found our minimum viable memory
            break
            
        except Exception as e:
            metrics['errors'].append(str(e))
            print(f"\nFailed with {factor*100}% memory allocation")
            print(f"Error: {str(e)}")
            continue
    
    if not successful_init:
        print("\nFailed to initialize with any memory setting")
        metrics['success_rate'] = 0.0
    
    return metrics

def setup_high_load() -> Dict[str, Any]:
    """Test initialization under high system load"""
    metrics = {}
    try:
        # Create CPU load
        import multiprocessing
        def cpu_load():
            while True:
                pass
        
        # Start CPU load processes
        processes = []
        for _ in range(multiprocessing.cpu_count()):
            p = multiprocessing.Process(target=cpu_load)
            p.start()
            processes.append(p)
        
        # Clear GPU memory
        clear_gpu_memory()
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        
        # Load model
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            device_map="auto",
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        
        # Collect metrics
        metrics["memory_usage"] = torch.cuda.memory_allocated() / (1024**3)  # GB
        metrics["gpu_utilization"] = torch.cuda.utilization() if hasattr(torch.cuda, 'utilization') else 0
        metrics["success_rate"] = 100
        
        # Cleanup CPU load processes
        for p in processes:
            p.terminate()
        
        return metrics
        
    except Exception as e:
        logger.error(f"High load test failed: {str(e)}")
        metrics["success_rate"] = 0
        metrics["error_type"] = type(e).__name__
        return metrics

def test_model_initialization():
    """Comprehensive block test for model initialization methods"""
    test_cases = [
        {
            "name": "current_implementation",
            "description": "Current implementation with both manual and auto initialization",
            "setup": setup_current_implementation,
            "metrics": ["init_time", "memory_usage", "gpu_utilization", "success_rate"]
        },
        {
            "name": "auto_only",
            "description": "Using only AutoModelForCausalLM's device_map='auto'",
            "setup": setup_auto_only,
            "metrics": ["init_time", "memory_usage", "gpu_utilization", "success_rate"]
        },
        {
            "name": "manual_only",
            "description": "Using only manual GPU initialization",
            "setup": setup_manual_only,
            "metrics": ["init_time", "memory_usage", "gpu_utilization", "success_rate"]
        },
        {
            "name": "low_memory",
            "description": "Test initialization with constrained memory settings",
            "setup": setup_low_memory,
            "metrics": ["init_time", "memory_usage", "gpu_utilization", "success_rate", "error_type"]
        },
        {
            "name": "high_load",
            "description": "Test initialization under high system load",
            "setup": setup_high_load,
            "metrics": ["init_time", "memory_usage", "gpu_utilization", "success_rate", "error_type"]
        }
    ]

    results = {}
    for test_case in test_cases:
        print(f"\nRunning test: {test_case['name']}")
        print(f"Description: {test_case['description']}")
        
        # Clear GPU memory before each test
        clear_gpu_memory()
        
        try:
            # Run test and collect metrics
            start_time = time.time()
            metrics = test_case['setup']()
            init_time = time.time() - start_time
            
            results[test_case['name']] = {
                "init_time": init_time,
                "memory_usage": metrics.get("memory_usage", 0),
                "gpu_utilization": metrics.get("gpu_utilization", 0),
                "success_rate": metrics.get("success_rate", 0),
                "error_type": metrics.get("error_type", None)
            }
            
            # Log results
            print(f"\nResults for {test_case['name']}:")
            print(f"Initialization time: {init_time:.2f} seconds")
            print(f"Memory usage: {metrics.get('memory_usage', 0):.2f} GB")
            print(f"GPU utilization: {metrics.get('gpu_utilization', 0)}%")
            print(f"Success rate: {metrics.get('success_rate', 0)}%")
            if metrics.get('error_type'):
                print(f"Error type: {metrics['error_type']}")
                
        except Exception as e:
            print(f"Test {test_case['name']} failed with error: {str(e)}")
            results[test_case['name']] = {
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        
        finally:
            # Clear GPU memory after each test
            clear_gpu_memory()
    
    return results

if __name__ == "__main__":
    print("Starting model initialization tests...")
    results = test_model_initialization()
    print("\nTest Summary:")
    for test_name, test_results in results.items():
        print(f"\n{test_name}:")
        for metric, value in test_results.items():
            print(f"  {metric}: {value}") 