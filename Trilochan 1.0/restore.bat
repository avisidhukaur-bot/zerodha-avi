@echo off
echo ===================================================
echo TRILOCHAN 1.0 RESTORE UTILITY (ZERODHA TRADING ENGINE)
echo ===================================================
echo This will overwrite all active Zerodha trading engine files
echo with the mature and stable Trilochan 1.0 release.
echo.
set /p confirm=Are you sure you want to proceed? (Y/N): 
if /i "%confirm%" neq "Y" (
    echo Restore cancelled.
    pause
    exit /b
)

echo Removing read-only attributes on destination files...
attrib -R ..\app.py 2>nul
attrib -R ..\block_manager.py 2>nul
attrib -R ..\check_db.py 2>nul
attrib -R ..\check_vps_log.py 2>nul
attrib -R ..\config.py 2>nul
attrib -R ..\db.py 2>nul
attrib -R ..\git_credentials.txt 2>nul
attrib -R ..\kite_executor.py 2>nul
attrib -R ..\lego0_diagnose.py 2>nul
attrib -R ..\lego1_deploy.py 2>nul
attrib -R ..\lego2_rollover.py 2>nul
attrib -R ..\main.py 2>nul
attrib -R ..\memory.md 2>nul
attrib -R ..\pnl_engine.py 2>nul
attrib -R ..\product_development_rollover.md 2>nul
attrib -R ..\requirements.txt 2>nul
attrib -R ..\secrets.txt 2>nul
attrib -R ..\secrets_template.txt 2>nul
attrib -R ..\telegram_bot.py 2>nul
attrib -R ..\test_brick1.py 2>nul
attrib -R ..\test_brick2.py 2>nul
attrib -R ..\test_brick3.py 2>nul
attrib -R ..\test_brick4.py 2>nul
attrib -R ..\test_brick5.py 2>nul
attrib -R ..\test_brick7.py 2>nul
attrib -R ..\utils.py 2>nul
attrib -R ..\zerodha_engine.log 2>nul
attrib -R ..\zerodha_instruments.csv 2>nul
attrib -R ..\ZERODHA_SETUP_GUIDE.md 2>nul
attrib -R ..\ZERODHA_SISTER_GUIDE.md 2>nul
attrib -R ..\zerodha_trader.db 2>nul
attrib -R ..\.gitignore 2>nul

echo Copying Trilochan 1.0 files to parent folder...
copy /Y app.py ..\
copy /Y block_manager.py ..\
copy /Y check_db.py ..\
copy /Y check_vps_log.py ..\
copy /Y config.py ..\
copy /Y db.py ..\
copy /Y git_credentials.txt ..\
copy /Y kite_executor.py ..\
copy /Y lego0_diagnose.py ..\
copy /Y lego1_deploy.py ..\
copy /Y lego2_rollover.py ..\
copy /Y main.py ..\
copy /Y memory.md ..\
copy /Y pnl_engine.py ..\
copy /Y product_development_rollover.md ..\
copy /Y requirements.txt ..\
copy /Y secrets.txt ..\
copy /Y secrets_template.txt ..\
copy /Y telegram_bot.py ..\
copy /Y test_brick1.py ..\
copy /Y test_brick2.py ..\
copy /Y test_brick3.py ..\
copy /Y test_brick4.py ..\
copy /Y test_brick5.py ..\
copy /Y test_brick7.py ..\
copy /Y utils.py ..\
copy /Y zerodha_engine.log ..\
copy /Y zerodha_instruments.csv ..\
copy /Y ZERODHA_SETUP_GUIDE.md ..\
copy /Y ZERODHA_SISTER_GUIDE.md ..\
copy /Y zerodha_trader.db ..\
copy /Y .gitignore ..\

echo.
echo ===================================================
echo TRILOCHAN 1.0 RESTORED SUCCESSFULLY!
echo ===================================================
pause
