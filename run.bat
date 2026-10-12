@echo off
REM Double-click to start Q-Nexus (run from Anaconda Prompt if "streamlit" is not found)
cd /d "%~dp0"
streamlit run app.py
pause
