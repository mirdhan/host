@echo off
REM Created by zvodd @ https://gist.github.com/zvodd
REM Set PythonDIR to your Python 3 install path; e.g. The folder with python.exe in it.
set PythonDIR=C:\Python3
set PATH=%PythonDIR%;%PythonDIR%\Scripts;%PATH%
set PYTHONPATH=%PythonDIR%\Lib;%PythonDIR%\Lib\site-packages;%PythonDIR%\DLLs;
set PATHEXT=%PATHEXT%;.PY;.PYW
assoc .py=Python.File>NUL
assoc .pyw=PythonW.File>NUL
ftype Python.File="%PythonDIR%\python.exe" %%1 %%*>NUL
ftype PythonW.File="%PythonDIR%\pythonw.exe" %%1 %%*>NUL
