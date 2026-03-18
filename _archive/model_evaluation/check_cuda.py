import torch

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda if torch.version.cuda else 'Not compiled with CUDA'}")
print(f"Number of GPUs: {torch.cuda.device_count()}")

if torch.cuda.is_available():
    print(f"GPU 0 name: {torch.cuda.get_device_name(0)}")
else:
    print("\nPyTorch was likely installed without CUDA support.")
    print("To install PyTorch with CUDA, visit: https://pytorch.org/get-started/locally/")
    print("Example: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
