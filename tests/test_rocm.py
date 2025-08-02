import torch

def test_rocm():
    print(f"PyTorch version: {torch.__version__}")
    print(f"GPU available: {torch.cuda.is_available()}")
    print(f"GPU device count: {torch.cuda.device_count()}")
    
    if torch.cuda.is_available():
        print(f"GPU Device Name: {torch.cuda.get_device_name()}")
        
        # Create tensors on GPU
        x = torch.rand(5, 5).to('cuda')
        y = torch.rand(5, 5).to('cuda')
        
        # Perform some operations
        z = x + y  # Addition
        print("\nGPU operation successful!")
        print(f"Sum of first elements: {z[0][0].item():.4f}")
    else:
        print("\nGPU is not available. Please check your installation.")

if __name__ == "__main__":
    test_rocm() 