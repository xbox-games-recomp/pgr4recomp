@echo off
rem Configure + build pgr4recomp against the installed ReXGlue SDK.
rem Usage: scripts\build.bat [release|debug|relwithdebinfo]   (default: release)
setlocal
set CFG=%~1
if "%CFG%"=="" set CFG=release
rem vcvars needs System32 + the VS Installer dir (vswhere) on PATH; tool shells may not provide them.
set PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\WindowsPowerShell\v1.0;C:\Program Files (x86)\Microsoft Visual Studio\Installer;C:\Program Files\Git\cmd
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set PATH=C:\Program Files\LLVM\bin;C:\Program Files\CMake\bin;C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%
cd /d "%~dp0.." || exit /b 1
cmake --preset win-amd64-%CFG% -DCMAKE_PREFIX_PATH="%~dp0..\..\_ext\rexglue-sdk\out\install\win-amd64" || exit /b 1
cmake --build --preset win-amd64-%CFG% || exit /b 1
echo BUILD_OK
