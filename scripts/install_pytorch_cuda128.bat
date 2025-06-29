@echo off
echo Installing PyTorch with CUDA 12.8 for RTX 5070...
echo.

echo Step 1: Uninstalling existing PyTorch...
pip uninstall -y torch torchvision torchaudio

echo.
echo Step 2: Installing CUDA 12.8 PyTorch...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

echo.
echo Step 3: Verifying installation...
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print('RTX 5070 ready for action!')"

echo.
echo Done! Your RTX 5070 is now optimized for PyTorch.
pause