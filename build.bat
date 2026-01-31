@echo off
chcp 936 >nul
echo [1/4] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python and add it to PATH!
    pause
    exit /b
)

echo [2/4] Installing dependencies (requests, Pillow, PyQt5, pyinstaller)...
pip install requests Pillow PyQt5 pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [3/4] Packaging program to .exe...
pyinstaller --onefile --windowed --add-data "hyw.ico;." --icon "hyw.ico" --name "SmartisanOS_Wallpaper_Downloader" wallpaper_downloader.py

if %errorlevel% equ 0 (
    echo.
    echo [4/4] Success! 
    echo The file is located in: dist\SmartisanOS_Wallpaper_Downloader.exe
) else (
    echo.
    echo Error: Packaging failed.
)

pause
