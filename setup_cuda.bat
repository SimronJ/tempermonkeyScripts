@echo off
set CUDA_PATH=E:\Cuda\cuda-toolkit
set CUDA_PATH_V12_6=E:\Cuda\cuda-toolkit
set PATH=%CUDA_PATH%\bin;%CUDA_PATH%\libnvvp;%PATH%
set LD_LIBRARY_PATH=%CUDA_PATH%\lib64;%LD_LIBRARY_PATH%

echo CUDA environment set up
echo CUDA_PATH: %CUDA_PATH%
echo.
echo Starting Python environment...
cd /d E:\github_clone\Tlopo_Boss_AutoFarm
call .venv\Scripts\activate
cmd