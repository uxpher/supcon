@echo off
REM ============================================================
REM Run with the supcon conda env python.
REM The default "python" in PATH is GTKWave's bundled python (no deps).
REM Usage:  run.bat scripts\11_capture_observation.py --task 3
REM ============================================================
"C:\Users\17765\my_model\miniconda3\envs\supcon\python.exe" %*
