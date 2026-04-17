@echo off
echo ============================================
echo  AR Hand Control - EXE Builder
echo ============================================

echo.
echo [1/2] Installing PyInstaller...
python -m pip install pyinstaller --quiet

echo.
echo [2/2] Building executable...
python -m PyInstaller ^
  --onedir ^
  --windowed ^
  --name ARHandControl ^
  --collect-all mediapipe ^
  --collect-all cv2 ^
  --hidden-import tkinter ^
  --hidden-import win32api ^
  main.py

echo.
echo ============================================
echo  Done!
echo  Your EXE is at: dist\ARHandControl\ARHandControl.exe
echo ============================================
pause
