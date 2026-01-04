@echo off
REM Cleanup Keywords - REAL RUN
REM Drag and drop a folder onto this file to clean up keywords

if "%~1"=="" (
    echo.
    echo Usage: Drag and drop a folder or file onto this batch file
    echo        OR run from command line: cleanup_keywords_run.bat "C:\path\to\images"
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo WARNING: This will MODIFY your files!
echo Target: %~1
echo ============================================================
echo.
set /p confirm="Are you sure you want to continue? (yes/no): "

if /i not "%confirm%"=="yes" (
    echo.
    echo Cleanup cancelled.
    echo.
    pause
    exit /b 0
)

echo.
echo Running cleanup on: %~1
echo.
python "%~dp0cleanup_old_keywords.py" "%~1"
echo.
echo Cleanup complete! Check the log file for details.
echo.
pause
