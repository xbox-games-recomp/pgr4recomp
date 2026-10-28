@echo off
rem Build + install the ReXGlue SDK from source (the prebuilt v0.10.0 zip is blocked by Defender).
rem Usage: scripts\build_sdk.bat [sdk_source_dir]
setlocal
set SDK=%~1
if "%SDK%"=="" set SDK=%~dp0..\..\_ext\rexglue-sdk
rem vcvars needs System32 + the VS Installer dir (vswhere) on PATH; tool shells may not provide them.
set PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\WindowsPowerShell\v1.0;C:\Program Files (x86)\Microsoft Visual Studio\Installer;C:\Program Files\Git\cmd
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set PATH=C:\Program Files\LLVM\bin;C:\Program Files\CMake\bin;C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%
cd /d "%SDK%" || exit /b 1
cmake --preset win-amd64 || exit /b 1
cmake --build out/build/win-amd64 --config Release --target install || exit /b 1
echo SDK_BUILD_OK
