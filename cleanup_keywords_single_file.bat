@echo off
REM Cleanup Keywords - Single File (with confirmation)
REM Drag and drop a single image file onto this batch file

if "%~1"=="" (
    echo.
    echo Usage: Drag and drop a single image file onto this batch file
    echo.
    pause
    exit /b 1
)

echo.
echo Testing single file: %~1
echo.
echo Running dry-run first...
python "%~dp0cleanup_old_keywords.py" "%~1" --dry-run --verbose
echo.
echo.
set /p confirm="Do you want to clean this file for real? (yes/no): "

if /i not "%confirm%"=="yes" (
    echo.
    echo Cleanup cancelled.
    echo.
    pause
    exit /b 0
)

echo.
echo Cleaning file...
python "%~dp0cleanup_old_keywords.py" "%~1"
echo.
echo Done!
echo.
pause
