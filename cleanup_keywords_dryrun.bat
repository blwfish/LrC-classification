@echo off
REM Cleanup Keywords - Dry Run
REM Drag and drop a folder onto this file to preview keyword cleanup

if "%~1"=="" (
    echo.
    echo Usage: Drag and drop a folder or file onto this batch file
    echo        OR run from command line: cleanup_keywords_dryrun.bat "C:\path\to\images"
    echo.
    pause
    exit /b 1
)

echo.
echo Running cleanup in DRY RUN mode on: %~1
echo.
python "%~dp0cleanup_old_keywords.py" "%~1" --dry-run --verbose
echo.
pause
