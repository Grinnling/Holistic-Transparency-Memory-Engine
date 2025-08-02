import logging
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

MODEL_PATH = Path("models/Qwen2.5-Coder-7B-Instruct")

def test_gpu():
    logger.info("Testing GPU availability...")
    logger.info(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA version: {torch.version.cuda}")
        logger.info(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    
    # Test ROCm
    if hasattr(torch.version, 'hip'):
        logger.info(f"ROCm version: {torch.version.hip}")
        
def test_model_load():
    logger.info(f"Testing model load from {MODEL_PATH}")
    logger.info(f"Model path contents: {list(MODEL_PATH.glob('*'))}")
    
    try:
        logger.info("Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH), trust_remote_code=True)
        logger.info("Tokenizer loaded successfully")
        
        logger.info("Loading model...")
        model = AutoModelForCausalLM.from_pretrained(
            str(MODEL_PATH),
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
            use_cache=True,
            local_files_only=True
        )
        logger.info("Model loaded successfully")
        logger.info(f"Model device: {model.device}")
        logger.info(f"Model dtype: {model.dtype}")
        
        # Try a simple inference
        logger.info("Testing inference...")
        inputs = tokenizer("print('Hello World')", return_tensors="pt").to(model.device)
        outputs = model.generate(**inputs, max_new_tokens=50)
        result = tokenizer.decode(outputs[0])
        logger.info(f"Test inference result: {result}")
        
    except Exception as e:
        logger.error(f"Error during model loading/testing: {str(e)}", exc_info=True)

if __name__ == "__main__":
    test_gpu()
    test_model_load() 