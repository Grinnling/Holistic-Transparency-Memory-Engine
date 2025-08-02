# OpenAI Compatible Server Setup Guide

## System Requirements
- Ubuntu 22.04 LTS or newer
- AMD GPU with ROCm support
- Docker installed
- Python 3.10 or newer

## Installation Steps

1. Run the Ubuntu setup script:
   ```bash
   chmod +x ubuntu_setup.sh
   ./ubuntu_setup.sh
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install Python requirements:
   ```bash
   pip install -r requirements.txt
   ```

4. Install PyTorch with ROCm support:
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
   ```

5. Restore project files and configurations from the backup directory:
   ```bash
   cp -r dev_backup_20250329_182153/projects/openaicompatible_server/* .
   ```

## Project Structure
```
openaicompatible_server/
├── server.py           # Main server implementation
├── test_rocm.py       # ROCm test script
├── requirements.txt   # Python dependencies
├── .env              # Environment variables
├── models/           # Model storage directory
└── venv/            # Python virtual environment
```

## Environment Variables
Create a `.env` file with the following variables:
```
OPENAI_API_KEY=your_api_key
MODEL_PATH=path_to_your_model
```

## Testing ROCm Support
Run the test script to verify ROCm support:
```bash
python test_rocm.py
```

## Development Notes
- The project uses ROCm for GPU acceleration
- Docker is used for containerized deployment
- VSCodium and PyCharm are recommended IDEs
- LM Studio is used for local model management

## Troubleshooting
1. If ROCm is not detected:
   - Check if ROCm is properly installed
   - Verify GPU compatibility
   - Check system logs for errors

2. If Docker issues occur:
   - Ensure Docker service is running
   - Check user permissions
   - Verify Docker installation

3. For Python environment issues:
   - Verify virtual environment is activated
   - Check Python version compatibility
   - Ensure all dependencies are installed

## Conversation History
This project was set up following a conversation about:
1. Initial attempts to install PyTorch with ROCm support
2. System migration from Manjaro to Ubuntu
3. Development environment setup
4. Security and system maintenance planning

## Additional Resources
- [ROCm Documentation](https://rocmdocs.amd.com/en/latest/)
- [PyTorch ROCm Guide](https://pytorch.org/docs/stable/notes/rocm.html)
- [Docker Documentation](https://docs.docker.com/) 