@echo off
rem Launch pgr4recomp for normal play. Double-click, or: play.bat [fullscreen] [extra cvars...]
rem   play.bat                 -> 1280x720 window
rem   play.bat fullscreen      -> fullscreen
rem   play.bat --window_width=1920 --window_height=1080
rem Log: work\play.log. Saves: <Documents>\pgr4recomp.
setlocal
set ROOT=%~dp0
set EXE=%ROOT%out\build\win-amd64-release\pgr4recomp.exe
if not exist "%EXE%" (
  echo pgr4recomp.exe not found - build it first with scripts\build.bat
  pause
  exit /b 1
)
set MODE=--fullscreen=false --window_width=1280 --window_height=720
if /i "%~1"=="fullscreen" (
  set MODE=--fullscreen=true
  shift
)
set EXTRA=
:args
if "%~1"=="" goto run
set EXTRA=%EXTRA% %1
shift
goto args
:run
pushd "%ROOT%out\build\win-amd64-release"
start "" "%EXE%" --game_data_root="%ROOT%assets" --log_file="%ROOT%work\play.log" %MODE%%EXTRA%
popd
