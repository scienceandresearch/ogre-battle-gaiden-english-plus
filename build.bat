@echo off
rem Builds the project with the Visual Studio 2022 C toolchain (CMake + Ninja).
setlocal
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
  echo vswhere.exe not found; install Visual Studio 2022 with the C++ build tools.
  exit /b 1
)
rem "call" keeps cmd from mangling the quoted path inside for /f
for /f "usebackq tokens=*" %%i in (`call "%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSINSTALL=%%i"
if not defined VSINSTALL (
  echo Visual Studio C++ build tools not found.
  exit /b 1
)
rem vcvars64 runs vswhere.exe by name, so put it on PATH
set "PATH=%PATH%;%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
call "%VSINSTALL%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
if not exist build\build.ninja cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo || exit /b 1
cmake --build build %* || exit /b 1
