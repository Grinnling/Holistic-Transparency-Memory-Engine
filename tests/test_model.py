import logging
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import time
import gc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('model_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_gpu_memory():
    """Log detailed GPU memory information"""
    if torch.cuda.is_available():
        memory_allocated = torch.cuda.memory_allocated() / 1024**3
        memory_reserved = torch.cuda.memory_reserved() / 1024**3
        max_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info(f"GPU Memory - Allocated: {memory_allocated:.2f}GB, Reserved: {memory_reserved:.2f}GB, Max: {max_memory:.2f}GB")

def clear_gpu_memory():
    """Clear GPU memory and cache"""
    if torch.cuda.is_available():
        # Clear memory cache
        torch.cuda.empty_cache()
        # Run garbage collection
        gc.collect()
        logger.info("Cleared GPU memory and cache")
        log_gpu_memory()

def test_model_loading():
    """Test model loading and basic inference"""
    try:
        # 1. Test model path
        model_path = Path("models/Qwen2.5-Coder-7B-Instruct")
        logger.info(f"Testing model path: {model_path}")
        if not model_path.exists():
            raise FileNotFoundError(f"Model path not found: {model_path}")
        
        # 2. Check CUDA availability
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available. Please check your GPU setup.")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        logger.info(f"Current CUDA device: {torch.cuda.current_device()}")
        logger.info(f"Device name: {torch.cuda.get_device_name()}")
        
        # 3. Clear and log GPU memory
        clear_gpu_memory()
        
        # 4. Load tokenizer
        logger.info("Loading tokenizer...")
        start_time = time.time()
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        tokenizer_time = time.time() - start_time
        logger.info(f"Tokenizer loaded successfully in {tokenizer_time:.2f} seconds")
        
        # 5. Load model
        logger.info("Loading model...")
        start_time = time.time()
        
        # Load model directly to GPU
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",  # Automatically handle device placement
            trust_remote_code=True,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True
        )
        
        model_time = time.time() - start_time
        logger.info(f"Model loaded successfully in {model_time:.2f} seconds")
        
        # Verify model device placement
        devices = set()
        for param in model.parameters():
            devices.add(param.device)
        logger.info(f"Model is distributed across devices: {devices}")
        
        # 6. Test basic inference
        logger.info("Testing basic inference...")
        test_prompt = "Write a simple Python function to add two numbers."
        logger.info(f"Test prompt: {test_prompt}")
        
        start_time = time.time()
        inputs = tokenizer(test_prompt, return_tensors="pt")
        inputs = {k: v.to(0) for k, v in inputs.items()}  # Move to GPU
        
        # Add debugging for input tensor
        logger.info(f"Input tensor shape: {inputs['input_ids'].shape}")
        logger.info(f"Input tensor device: {inputs['input_ids'].device}")
        
        try:
            with torch.no_grad():
                # First, get the logits
                outputs = model(**inputs)
                logits = outputs.logits
                
                # Check for NaN or inf in logits
                if torch.isnan(logits).any() or torch.isinf(logits).any():
                    logger.error("NaN or inf detected in logits")
                    return False
                
                # Generate with more conservative parameters
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=50,
                    temperature=0.7,
                    top_p=0.95,
                    do_sample=True,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    repetition_penalty=1.1,
                    num_return_sequences=1,
                    early_stopping=True
                )
            
            inference_time = time.time() - start_time
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            logger.info(f"Inference completed in {inference_time:.2f} seconds")
            logger.info(f"Model response: {response}")
            
            # Log final GPU memory state
            log_gpu_memory()
            
        except Exception as e:
            logger.error(f"Error during generation: {str(e)}", exc_info=True)
            logger.info(f"Model device: {next(model.parameters()).device}")
            logger.info(f"Model dtype: {next(model.parameters()).dtype}")
            raise
        
        return True
        
    except Exception as e:
        logger.error(f"Error during model testing: {str(e)}", exc_info=True)
        return False
    finally:
        # Always try to clear GPU memory when done
        clear_gpu_memory()

if __name__ == "__main__":
    logger.info("Starting model test...")
    success = test_model_loading()
    if success:
        logger.info("Model test completed successfully!")
    else:
        logger.error("Model test failed!") 