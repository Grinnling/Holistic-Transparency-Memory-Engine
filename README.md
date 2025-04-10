# OpenAI-Compatible Server with AMD GPU Support

This project provides a Flask-based web server that emulates the OpenAI API for chat completions, specifically optimized to run large language models on AMD GPUs using ROCm.

## Features

*   **OpenAI API Compatibility:** Implements `/v1/chat/completions` and `/v1/models` endpoints.
*   **AMD GPU Optimization:** Utilizes PyTorch with ROCm backend for efficient execution on AMD hardware.
*   **Streaming Responses:** Supports chunked responses for chat completions.
*   **Environment Configuration:** Uses `.env` file for easy setup of API keys, model paths, and other settings.
*   **Rate Limiting:** Basic rate limiting included.
*   **Section-Specific Logging:** Detailed logging with error codes for easier debugging.
*   **System Monitoring:** Basic monitoring of CPU, Memory, and GPU resources.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd openaicompatible_server
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure Environment:**
    *   Copy the example environment file: `cp .env.example .env`
    *   Edit the `.env` file:
        *   Set `OPENAI_COMPATIBILITY_API_KEY` (Base64 encoded API key).
        *   Set `OPENAI_COMPATIBILITY_USERNAME` (Base64 encoded username).
        *   Ensure `MODEL_PATH` points to your downloaded model directory (e.g., `./models/YourModelName`).
        *   Adjust `MAX_TOKENS`, `TEMPERATURE`, `TOP_P`, `RATE_LIMIT` as needed.
5.  **Download Model:**
    *   Make sure the language model specified in `MODEL_PATH` is downloaded and placed correctly.
    *   Create the `./models/` and `./offload/` directories if they don't exist.

## Running the Server

```bash
python server.py
```

The server will start, load the model (this might take some time), and listen on `http://0.0.0.0:5001` (or as configured in `.env`).

## Usage

Send requests to the `/v1/chat/completions` endpoint using the OpenAI API format. Ensure you provide the correct `Authorization` header (Basic or Bearer using the credentials from `.env`).

**Example using curl:**

```bash
# Using Basic Auth (replace user:pass with your base64 encoded username:apikey)
curl http://localhost:5001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic dGVzdDp0ZXN0" \
  -d '{
    "model": "Qwen2.5-Coder-7B-Instruct", 
    "messages": [{"role": "user", "content": "Write a hello world in Python"}],
    "max_tokens": 50,
    "temperature": 0.7
  }'

# Using Bearer Token (replace your_base64_encoded_api_key)
curl http://localhost:5001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dGVzdA==" \
  -d '{
    "model": "Qwen2.5-Coder-7B-Instruct", 
    "messages": [{"role": "user", "content": "Write a hello world in Python"}],
    "max_tokens": 50,
    "temperature": 0.7
  }'
```

## Logging

*   General server logs are in `server.log`.
*   Section-specific logs (auth, model, memory, etc.) are in the `logs/` directory.

## Contributing

(Add contribution guidelines here if desired)

## License

(Add license information here) 