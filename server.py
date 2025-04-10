# server.py
from flask import Flask, request, jsonify, Response
import logging
from dotenv import load_dotenv
import os
from flask_talisman import Talisman
import base64
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
import torch
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import timedelta
from pathlib import Path
import time
import json
import gc
from functools import wraps
import threading
from queue import Queue
import psutil
import signal
import sys
from datetime import datetime
import traceback
from error_logging import (
    auth_logger, model_logger, memory_logger, request_logger,
    response_logger, cleanup_logger, health_logger, ErrorCodes
)

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Rate limiting setup
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Load configuration from environment
API_KEY = os.getenv("OPENAI_COMPATIBILITY_API_KEY", "dGVzdA==")  # base64 encoded "test"
API_USERNAME = os.getenv("OPENAI_COMPATIBILITY_USERNAME", "dGVzdA==")  # base64 encoded "test"
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "Qwen2.5-Coder-7B-Instruct")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
TOP_P = float(os.getenv("TOP_P", "0.95"))
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "100"))

# Debug logging for environment variables
logger.info(f"Loaded API_KEY: {API_KEY}")
logger.info(f"Loaded API_USERNAME: {API_USERNAME}")
logger.info(f"Loaded MODEL_PATH: {MODEL_PATH}")
logger.info(f"Loaded MAX_TOKENS: {MAX_TOKENS}")
logger.info(f"Loaded TEMPERATURE: {TEMPERATURE}")
logger.info(f"Loaded TOP_P: {TOP_P}")
logger.info(f"Loaded RATE_LIMIT: {RATE_LIMIT}")

# Global variables
model = None
tokenizer = None
model_loaded = False  # Flag to track model loading status
model_lock = threading.Lock()
request_queue = Queue()
processing_thread = None
last_health_check = datetime.now()
system_monitor_thread = None
should_stop = False

def check_system_resources():
    """Check system resources and log if critical"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        if torch.cuda.is_available():
            gpu_memory = torch.cuda.memory_allocated() / (1024**3)  # Convert to GB
            gpu_memory_reserved = torch.cuda.memory_reserved() / (1024**3)
            gpu_memory_max = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            
            health_logger.log_info(
                "HEALTH-001",
                f"System Resources - CPU: {cpu_percent}%, Memory: {memory_percent}%, GPU Allocated: {gpu_memory:.2f}GB"
            )
            
            # Check if GPU memory usage is above 95%
            if gpu_memory > (gpu_memory_max * 0.95):
                health_logger.log_error(
                    ErrorCodes.HEALTH_CRITICAL,
                    "Critical resource usage detected!",
                    {
                        "gpu_memory": gpu_memory,
                        "gpu_memory_reserved": gpu_memory_reserved,
                        "gpu_memory_max": gpu_memory_max
                    }
                )
                return True
        else:
            health_logger.log_info(
                "HEALTH-002",
                f"System Resources - CPU: {cpu_percent}%, Memory: {memory_percent}%"
            )
            
        return False
    except Exception as e:
        health_logger.log_error(
            ErrorCodes.HEALTH_MONITOR_ERROR,
            f"Error checking system resources: {str(e)}",
            {"traceback": traceback.format_exc()}
        )
        return False

def system_monitor():
    """Monitor system resources and take action if needed"""
    global should_stop, last_health_check
    while not should_stop:
        try:
            resources = check_system_resources()
            if resources:
                # Log resource usage
                logger.info(f"System Resources - CPU: {resources['cpu_percent']}%, "
                          f"Memory: {resources['memory_percent']}%, "
                          f"GPU Allocated: {resources['gpu_memory']['allocated']:.2f}GB")
                
                # Take action if resources are critically high
                if (resources['cpu_percent'] > 90 or 
                    resources['memory_percent'] > 90 or 
                    resources['gpu_memory']['allocated'] > resources['gpu_memory']['total'] * 0.85):
                    logger.warning("Critical resource usage detected!")
                    clear_gpu_memory()
                
                # Update health check timestamp
                last_health_check = datetime.now()
                    
        except Exception as e:
            logger.error(f"Error in system monitor: {str(e)}")
        time.sleep(10)  # Increased sleep time to reduce monitoring overhead

def emergency_recovery():
    """Emergency recovery procedure"""
    global model, tokenizer
    logger.warning("Initiating emergency recovery")
    
    if model is not None and tokenizer is not None:
        logger.info("Model and tokenizer are already loaded. Skipping reload.")
        return True

    try:
        # Clear GPU memory
        clear_gpu_memory()
        
        # Clear request queue
        while not request_queue.empty():
            try:
                request_queue.get_nowait()
            except:
                pass
        
        # Reset model if possible
        if model is not None:
            try:
                del model
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except:
                pass
        
        # Reload model
        model = None
        tokenizer = None
        if load_model():
            logger.info("Emergency recovery completed successfully")
            return True
        else:
            logger.error("Failed to reload model during recovery")
            return False
            
    except Exception as e:
        logger.error(f"Emergency recovery failed: {str(e)}")
        return False

def clear_gpu_memory():
    """Clear GPU memory and release resources"""
    global model, tokenizer, model_loaded
    
    if torch.cuda.is_available():
        logger.info("Clearing GPU memory...")
        if model is not None:
            del model
            model = None
        if tokenizer is not None:
            del tokenizer
            tokenizer = None
        torch.cuda.empty_cache()
        gc.collect()
        torch.cuda.empty_cache()  # Double clear to ensure memory is freed
        model_loaded = False
        logger.info("GPU memory cleared and model state reset")

def log_gpu_memory():
    """Log detailed GPU memory information"""
    if torch.cuda.is_available():
        memory_allocated = torch.cuda.memory_allocated() / 1024**3
        memory_reserved = torch.cuda.memory_reserved() / 1024**3
        max_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info(f"GPU Memory - Allocated: {memory_allocated:.2f}GB, "
                   f"Reserved: {memory_reserved:.2f}GB, Max: {max_memory:.2f}GB")
        return memory_allocated

def unified_model_initialization(max_retries=3, backoff_time=5):
    """Unified model initialization with error recovery"""
    global model, tokenizer, model_loaded
    
    # Skip if already loaded
    if model_loaded:
        model_logger.log_info("MODEL-001", "Model already loaded. Skipping reload.")
        return True
    
    for attempt in range(max_retries):
        try:
            # Clear any existing model and memory
            if model is not None:
                model_logger.log_info("MODEL-002", "Clearing existing model...")
                del model
                model = None
            if tokenizer is not None:
                model_logger.log_info("MODEL-003", "Clearing existing tokenizer...")
                del tokenizer
                tokenizer = None
            
            # Clear GPU memory aggressively for AMD
            if torch.cuda.is_available():
                model_logger.log_info("MODEL-004", "Initializing AMD GPU...")
                torch.cuda.empty_cache()
                gc.collect()
                torch.cuda.empty_cache()  # Double clear to ensure memory is freed
                
                # Calculate 90% of available memory
                total_memory = torch.cuda.get_device_properties(0).total_memory
                allocated_memory = int(total_memory * 0.9)  # 90% of total memory
                model_logger.log_info("MODEL-012", f"Setting memory allocation to {allocated_memory / (1024**3):.2f} GB")
                
                # Configure memory settings
                torch.cuda.set_per_process_memory_fraction(0.9)  # 90% memory fraction
                max_memory = {0: f"{allocated_memory // (1024**3)}GB"}
                
                gpu_info = {
                    "device_count": torch.cuda.device_count(),
                    "current_device": torch.cuda.current_device(),
                    "device_name": torch.cuda.get_device_name(),
                    "total_memory": total_memory / (1024**3),
                    "allocated_memory": allocated_memory / (1024**3),
                    "memory_fraction": 0.9
                }
                model_logger.log_info("MODEL-005", "GPU initialization complete", gpu_info)
            
            # Load tokenizer first
            model_logger.log_info("MODEL-006", "Loading tokenizer...")
            tokenizer = AutoTokenizer.from_pretrained(
                MODEL_PATH,
                trust_remote_code=True,
                use_fast=True
            )
            model_logger.log_info("MODEL-007", "Tokenizer loaded successfully")
            
            # Load model with AMD-optimized settings
            model_logger.log_info("MODEL-008", "Attempting to load model with AMD-optimized settings...")
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_PATH,
                trust_remote_code=True,
                torch_dtype=torch.float16,
                device_map="auto",
                max_memory=max_memory,
                offload_folder="offload",
                offload_state_dict=True,
                low_cpu_mem_usage=True
            )
            model_logger.log_info("MODEL-009", "Model loaded successfully with AMD optimizations")
            model_loaded = True
            return True
            
        except Exception as e:
            error_context = {
                "attempt": attempt + 1,
                "max_retries": max_retries,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            model_logger.log_error(
                ErrorCodes.MODEL_INIT_FAILED,
                f"Model initialization attempt {attempt + 1} failed",
                error_context
            )
            
            if attempt < max_retries - 1:
                model_logger.log_info("MODEL-013", f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff
            else:
                model_logger.log_error(
                    ErrorCodes.MODEL_INIT_FAILED,
                    "All initialization attempts failed",
                    error_context
                )
                return False
    
    return False

# Update load_model to use the unified initialization
def load_model():
    """Load the model and tokenizer with AMD GPU optimizations"""
    return unified_model_initialization()

def log_memory_state(context):
    """Log current memory state with context"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info(f"Memory State [{context}] - Allocated: {allocated:.2f}GB, Reserved: {reserved:.2f}GB, Total: {total:.2f}GB")

def process_request(request_data):
    """Process a single request"""
    try:
        # Extract request parameters
        messages = request_data.get("messages", [])
        max_tokens = request_data.get("max_tokens", MAX_TOKENS)
        temperature = request_data.get("temperature", TEMPERATURE)
        
        # Generate prompt from messages
        prompt = ""
        system_message = ""
        
        # Extract system message if present
        for message in messages:
            if message.get("role") == "system":
                system_message = message.get("content", "")
                break
                
        # Add system message with English instruction
        if system_message:
            prompt += f"System: {system_message}\nPlease respond in English by default, unless specifically requested to use another language.\n"
            
        # Add only the last user message
        for message in reversed(messages):
            if message.get("role") == "user":
                prompt += f"Human: {message.get('content', '')}\n"
                break
                
        prompt += "Assistant: "
        request_logger.log_info("REQ-001", f"Generated prompt: {prompt}")

        # Process the request
        try:
            request_logger.log_info("REQ-002", "Tokenizing input...")
            inputs = tokenizer(prompt, return_tensors="pt").to(torch.cuda.current_device())
            request_logger.log_info("REQ-003", f"Input tokens shape: {inputs['input_ids'].shape}")
            
            request_logger.log_info("REQ-004", "Starting model generation...")
            start_time = time.time()
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=TOP_P,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
            generation_time = time.time() - start_time
            
            request_logger.log_info("REQ-005", f"Generation completed in {generation_time:.2f} seconds")
            request_logger.log_info("REQ-006", f"Output shape: {outputs.shape}")
            
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            request_logger.log_info("REQ-007", f"Response length: {len(response)} characters")
            
            return response
            
        except Exception as e:
            request_logger.log_error(
                ErrorCodes.REQ_PROCESSING_ERROR,
                f"Error processing request: {str(e)}",
                {"traceback": traceback.format_exc()}
            )
            return None
            
    except Exception as e:
        request_logger.log_error(
            ErrorCodes.REQ_INVALID_FORMAT,
            f"Invalid request format: {str(e)}",
            {"traceback": traceback.format_exc()}
        )
        return None

def generate_response(model, tokenizer, prompt, max_tokens=2048, temperature=0.7, top_p=0.95):
    """Generate response with memory monitoring"""
    try:
        # Log initial memory state
        initial_memory = log_gpu_memory()
        model_logger.log_info("MODEL-014", f"Initial memory state: {initial_memory / (1024**3):.2f} GB")
        
        # Prepare inputs
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        
        # Log memory after input preparation
        prep_memory = log_gpu_memory()
        model_logger.log_info("MODEL-015", f"Memory after input preparation: {prep_memory / (1024**3):.2f} GB")
        
        # Generate response
        outputs = model.generate(
            **inputs,
            max_length=max_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True
        )
        
        # Log memory after generation
        gen_memory = log_gpu_memory()
        model_logger.log_info("MODEL-016", f"Memory after generation: {gen_memory / (1024**3):.2f} GB")
        
        # Decode response
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Log final memory state
        final_memory = log_gpu_memory()
        model_logger.log_info("MODEL-017", f"Final memory state: {final_memory / (1024**3):.2f} GB")
        
        # Calculate memory usage metrics
        peak_usage = max(initial_memory, prep_memory, gen_memory, final_memory)
        model_logger.log_info("MODEL-018", f"Peak memory usage: {peak_usage / (1024**3):.2f} GB")
        
        return response
    except Exception as e:
        model_logger.log_error(ErrorCodes.RESPONSE_GEN_FAILED, f"Response generation failed: {str(e)}")
        raise

def request_processor():
    """Process requests from the queue"""
    while True:
        try:
            if not request_queue.empty():
                request_data = request_queue.get()
                logger.info("Processing request from queue...")
                
                try:
                    # Generate response
                    response = process_request(request_data)
                    
                    # Send response back to client
                    request_data['callback'](response)
                    
                except Exception as e:
                    logger.error(f"Error processing request: {str(e)}")
                    request_data['callback'](jsonify({"error": str(e)}), 500)
                
                request_queue.task_done()
            
            time.sleep(0.1)  # Small delay to prevent CPU spinning
            
        except Exception as e:
            logger.error(f"Error in request processor: {str(e)}")
            time.sleep(1)  # Longer delay on error

def initialize_server():
    """Initialize the server and load the model"""
    global model, tokenizer, model_loaded
    
    try:
        # Configure GPU backend based on available hardware
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name()
            model_logger.log_info("MODEL-010", f"Initializing GPU: {gpu_name}")
            
            if "AMD" in gpu_name:
                model_logger.log_info("MODEL-011", "Configuring ROCm backend for AMD GPU...")
                torch.backends.cudnn.enabled = False  # Disable cuDNN (NVIDIA-specific)
                torch.backends.mps.enabled = True  # Enable ROCm backend for AMD GPUs
            else:
                model_logger.log_info("MODEL-012", "Using CUDA backend for NVIDIA GPU...")
                # Future NVIDIA-specific optimizations will go here
        
        # Start system monitor thread
        monitor_thread = threading.Thread(target=system_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Load model once during initialization
        if not load_model():
            model_logger.log_error(
                ErrorCodes.MODEL_LOAD_FAILED,
                "Failed to load model during initialization"
            )
            return False
        
        # Start request processor thread
        processor_thread = threading.Thread(target=request_processor)
        processor_thread.daemon = True
        processor_thread.start()
        
        return True
    
    except Exception as e:
        model_logger.log_error(
            ErrorCodes.MODEL_INIT_FAILED,
            f"Server initialization failed: {str(e)}",
            {"traceback": traceback.format_exc()}
        )
        return False

def cleanup():
    """Cleanup function for graceful shutdown"""
    global should_stop
    should_stop = True
    
    try:
        # Wait for threads to finish
        if processing_thread:
            processing_thread.join(timeout=5)
        if system_monitor_thread:
            system_monitor_thread.join(timeout=5)
            
        # Clear GPU memory
        if torch.cuda.is_available():
            cleanup_logger.log_info("CLEAN-001", "Clearing GPU memory during shutdown")
            torch.cuda.empty_cache()
            gc.collect()
            
        cleanup_logger.log_info("CLEAN-002", "Server shutdown completed successfully")
    except Exception as e:
        cleanup_logger.log_error(
            ErrorCodes.CLEAN_RESOURCE_FAILED,
            f"Error during server cleanup: {str(e)}",
            {"traceback": traceback.format_exc()}
        )

# Register cleanup handler
signal.signal(signal.SIGTERM, lambda sig, frame: cleanup())
signal.signal(signal.SIGINT, lambda sig, frame: cleanup())

# Enhanced Content Security Policy (CSP)
csp = {
    'default-src': "'self'",
    'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': "'self' data:",
    'frame-ancestors': "'self'",
    'form-action': "'self'",
    'base-uri': "'self'",
    'object-src': "'self'",
    'media-src': "'self'",
    'connect-src': ["'self'", "https://*"],
    'font-src': "'self' data:",
    'frame-src': "'self'"
}

# Add raw connection logging
@app.before_request
def log_raw_request():
    logger.info(f"Raw request received from {request.remote_addr}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request URL: {request.url}")
    if request.is_json:
        logger.info(f"Request body: {request.get_json()}")
    return None

# Initialize Talisman with enhanced security
Talisman(
    app,
    content_security_policy=csp,
    force_https=False,  # Disable HTTPS forcing
    strict_transport_security=False,  # Disable HSTS
    session_cookie_secure=False,  # Allow non-HTTPS cookies
    session_cookie_http_only=True,
    session_cookie_samesite='Lax'
)

def authenticate(username, password):
    """Authenticate the request"""
    try:
        if not username or not password:
            auth_logger.log_error(
                ErrorCodes.AUTH_MISSING_HEADERS,
                "Missing authentication headers"
            )
            return False
            
        expected_username = base64.b64decode(API_USERNAME).decode('utf-8')
        expected_password = base64.b64decode(API_KEY).decode('utf-8')
        
        if username != expected_username or password != expected_password:
            auth_logger.log_error(
                ErrorCodes.AUTH_INVALID_CREDENTIALS,
                "Invalid credentials provided"
            )
            return False
            
        auth_logger.log_info("AUTH-001", "Authentication successful")
        return True
    except Exception as e:
        auth_logger.log_error(
            ErrorCodes.AUTH_INVALID_FORMAT,
            f"Authentication error: {str(e)}",
            {"traceback": traceback.format_exc()}
        )
        return False

@app.before_request
def check_authentication():
    log_memory_state("Before Auth")
    auth_header = request.headers.get("Authorization")
    logger.info(f"Received auth header: {auth_header}")

    if not auth_header:
        logger.warning("Missing authorization header in request.")
        return jsonify({"error": "Missing authorization header"}), 401

    try:
        # Handle Bearer token
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            logger.info(f"Received Bearer token: {token}")
            if token == base64.b64decode(API_KEY).decode('utf-8'):
                logger.info("Bearer token authentication successful")
                log_memory_state("After Bearer Auth")
                return None
            else:
                logger.warning("Invalid Bearer token")
                return jsonify({"error": "Invalid Bearer token"}), 401

        # Handle Basic Auth
        if auth_header.startswith("Basic "):
            encoded_auth = auth_header.split(" ")[1]
            logger.info(f"Encoded auth: {encoded_auth}")
            decoded_auth = base64.b64decode(encoded_auth).decode('utf-8')
            logger.info(f"Decoded auth: {decoded_auth}")
            username, password = decoded_auth.split(":")
            logger.info(f"Username: {username}, Password length: {len(password)}")
            
            if authenticate(username, password):
                logger.info("Basic auth successful")
                log_memory_state("After Basic Auth")
                return None
            else:
                logger.warning(f"Invalid credentials provided. Expected username: {API_USERNAME}")
                return jsonify({"error": "Invalid credentials"}), 401

        logger.warning("Unsupported authentication method")
        return jsonify({"error": "Unsupported authentication method"}), 401

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return jsonify({"error": "Authentication failed"}), 401

@app.before_request
def log_request_info():
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request IP: {request.remote_addr}")
    logger.info(f"Request Headers: {dict(request.headers)}")

# Health Check Endpoint
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "Server is up and running"}), 200

# OpenAI-compatible endpoints
@app.route("/v1/models", methods=["GET"])
@limiter.limit("100 per minute")
def list_models():
    return jsonify({
        "data": [
            {
                "id": MODEL_PATH.name,
                "object": "model",
                "created": 1686935002,
                "owned_by": "openai",
                "permission": [],
                "root": MODEL_PATH.name,
                "parent": None
            }
        ],
        "object": "list"
    })

@app.route("/v1/chat/completions", methods=["POST"])
@limiter.limit(f"{RATE_LIMIT}/minute")
def chat_completions():
    log_memory_state("Before Request Processing")
    if model is None or tokenizer is None:
        return jsonify({"error": "Model not loaded"}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        messages = data.get("messages", [])
        if not messages:
            return jsonify({"error": "No messages provided"}), 400

        temperature = data.get("temperature", 0.7)
        max_tokens = min(data.get("max_tokens", 1000), 4000)  # Cap max tokens

        # Convert messages to prompt using Qwen's chat format
        prompt = ""
        system_message = None
        
        # First, find the system message
        for message in messages:
            if message.get("role") == "system":
                system_message = message.get("content", "")
                break
                
        # Add system message with English instruction
        if system_message:
            prompt += f"System: {system_message}\nPlease respond in English by default, unless specifically requested to use another language.\n"
            
        # Add only the last user message
        for message in reversed(messages):
            if message.get("role") == "user":
                prompt += f"Human: {message.get('content', '')}\n"
                break
                
        prompt += "Assistant: "
        logger.info(f"Generated prompt: {prompt}")

        # Process the request
        logger.info("Tokenizing input...")
        inputs = tokenizer(prompt, return_tensors="pt").to(torch.cuda.current_device())
        logger.info(f"Input tokens shape: {inputs['input_ids'].shape}")
        
        logger.info("Starting model generation...")
        start_time = time.time()
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=TOP_P,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id
        )
        generation_time = time.time() - start_time
        
        logger.info(f"Generation completed in {generation_time:.2f} seconds")
        logger.info(f"Output shape: {outputs.shape}")
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.info(f"Response length: {len(response)} characters")
        
        # Get model name from path
        model_name = os.path.basename(MODEL_PATH)

        def generate_chunks():
            # Send the response in chunks
            chunk_size = 50  # Adjust this value as needed
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i + chunk_size]
                chunk_data = {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }
                    ]
                }
                logger.info(f"Sending chunk: {chunk_data}")
                yield f"data: {json.dumps(chunk_data)}\n\n"
                time.sleep(0.1)  # Add a small delay between chunks

            # Send the final message
            final_data = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }
                ]
            }
            logger.info(f"Sending final chunk: {final_data}")
            yield f"data: {json.dumps(final_data)}\n\n"
            yield "data: [DONE]\n\n"

        return Response(generate_chunks(), mimetype='text/event-stream')

    except Exception as e:
        log_memory_state("Error State")
        logger.error(f"Error in chat completion: {e}")
        return jsonify({"error": str(e)}), 500

# Add CORS support
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/v1/chat/completions', methods=['OPTIONS'])
def handle_options():
    return '', 204

def generate(prompt, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, top_p=TOP_P):
    """Generate a response from the model"""
    try:
        logger.info("Tokenizing input...")
        inputs = tokenizer(prompt, return_tensors="pt").to(torch.cuda.current_device())
        logger.info(f"Input tokens shape: {inputs['input_ids'].shape}")
        
        logger.info("Starting model generation...")
        logger.info(f"Memory State [Before Generation] - Allocated: {torch.cuda.memory_allocated() / 1024**3:.2f}GB, Reserved: {torch.cuda.memory_reserved() / 1024**3:.2f}GB, Total: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f}GB")
        
        start_time = time.time()
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id
        )
        generation_time = time.time() - start_time
        
        logger.info(f"Generation completed in {generation_time:.2f} seconds")
        logger.info(f"Output shape: {outputs.shape}")
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.info(f"Response length: {len(response)} characters")
        
        logger.info(f"Memory State [End of Request Processing] - Allocated: {torch.cuda.memory_allocated() / 1024**3:.2f}GB, Reserved: {torch.cuda.memory_reserved() / 1024**3:.2f}GB, Total: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f}GB")
        
        # Get the model name from the path
        model_name = os.path.basename(MODEL_PATH)
        
        def generate_response():
            yield json.dumps({
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_name,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": inputs['input_ids'].shape[1],
                    "completion_tokens": outputs.shape[1] - inputs['input_ids'].shape[1],
                    "total_tokens": outputs.shape[1]
                }
            }) + "\n"
            
        return Response(generate_response(), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error during generation: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    try:
        if initialize_server():
            model_logger.log_info("MODEL-013", "Server initialized successfully")
            app.run(
                host=os.getenv("HOST", "0.0.0.0"),
                port=int(os.getenv("PORT", "5001")),
                debug=True,
                use_reloader=False
            )
    except Exception as e:
        model_logger.log_error(
            ErrorCodes.MODEL_INIT_FAILED,
            f"Critical server error: {str(e)}",
            {"traceback": traceback.format_exc()}
        )
        sys.exit(1)