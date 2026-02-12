@echo off
REM DTIC Scraper Quick Start Script for Windows
REM This script provides an easy way to run the scraper

echo ========================================
echo DTIC Publication Scraper
echo ========================================
echo.

:menu
echo Select an option:
echo   1. Verify setup
echo   2. Run test scrape (5 publications, visible browser)
echo   3. Run small scrape (20 publications, headless)
echo   4. Run medium scrape (100 publications, headless)
echo   5. Resume previous scrape
echo   6. Analyze scraped data
echo   7. View examples
echo   8. Exit
echo.

set /p choice="Enter your choice (1-8): "

if "%choice%"=="1" goto verify
if "%choice%"=="2" goto test
if "%choice%"=="3" goto small
if "%choice%"=="4" goto medium
if "%choice%"=="5" goto resume
if "%choice%"=="6" goto analyze
if "%choice%"=="7" goto examples
if "%choice%"=="8" goto end
echo Invalid choice. Please try again.
goto menu

:verify
echo.
echo Running setup verification...
python verify_setup.py
pause
goto menu

:test
echo.
echo Running test scrape (5 publications, visible browser)...
python scraper.py --max-publications 5 --no-headless
pause
goto menu

:small
echo.
echo Running small scrape (20 publications)...
python scraper.py --max-publications 20
pause
goto menu

:medium
echo.
echo Running medium scrape (100 publications)...
python scraper.py --max-publications 100
pause
goto menu

:resume
echo.
echo Resuming previous scrape...
python scraper.py --resume
pause
goto menu

:analyze
echo.
echo Analyzing scraped data...
python analyze.py
pause
goto menu

:examples
echo.
echo Running examples...
python examples.py
pause
goto menu

:end
echo.
echo Goodbye!
