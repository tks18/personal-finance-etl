@echo off
setlocal

:: =====================================================================
:: Personal Finance ETL - Unattended Cron Execution Script
:: =====================================================================

:: Change this to your compiled cli.exe or keep as "uv run shan-fin"
set "CLI_EXECUTABLE=uv run shan-fin"

:: Configuration Paths
set "CONFIG_PATH=D:\Path\To\Settings\config.toml"
set "RULES_PATH=D:\Path\To\Financial\rules.toml"

echo [%DATE% %TIME%] [Cron Job] Starting Personal Finance ETL Pipeline...
echo [%DATE% %TIME%] Executable: %CLI_EXECUTABLE%
echo ---------------------------------------------------------------------

"%CLI_EXECUTABLE%" cli --config="%CONFIG_PATH%" --rules="%RULES_PATH%" --auto --cron

if %ERRORLEVEL% equ 0 (
    echo [%DATE% %TIME%] [Cron Job] Pipeline completed successfully.
) else (
    echo [%DATE% %TIME%] [Cron Job] Pipeline failed with error code %ERRORLEVEL%.
)

:: Wait for 10 seconds before closing
timeout /t 10

endlocal
