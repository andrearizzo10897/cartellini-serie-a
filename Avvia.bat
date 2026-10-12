@echo off
cd /d "%~dp0"
REM Avvia il server e apre la pagina. Prova "python" nel PATH, poi le cartelle tipiche di Anaconda.
where python >nul 2>nul
if %errorlevel%==0 (
  python server.py %*
  goto fine
)
for %%P in ("%USERPROFILE%\anaconda3\python.exe" "%USERPROFILE%\Anaconda3\python.exe" "%USERPROFILE%\miniconda3\python.exe" "C:\ProgramData\anaconda3\python.exe" "C:\ProgramData\Anaconda3\python.exe") do (
  if exist %%P (
    %%P server.py %*
    goto fine
  )
)
echo Python non trovato. Apri "Anaconda Prompt", vai in questa cartella e lancia: python server.py
:fine
echo.
pause
