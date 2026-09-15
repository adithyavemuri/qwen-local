# Windows setup

The Windows installer is a PowerShell counterpart to `setup_qwen.sh`. It keeps
the source, compiled runtime, downloads, and model inside this folder.

## One-time prerequisites

Install:

1. Windows 10 or 11 on x64 hardware.
2. Python 3.
3. Git for Windows.
4. Visual Studio 2022 Community or Build Tools with **Desktop development with
   C++** and **C++ CMake tools for Windows** selected.
5. At least 25 GB of free disk space; more is preferable for build files.

The setup script itself does not install Windows software and does not request
administrator privileges. Installing Visual Studio or Git may require the
computer owner's normal installation permissions.

## Build and download

Open **Developer PowerShell for VS 2022**, change to this folder, and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_qwen.ps1 -Preflight
.\setup_qwen.ps1
```

The execution-policy change applies only to that PowerShell process. You may
instead use your organization's approved script-signing policy.

Build or download separately:

```powershell
.\setup_qwen.ps1 -RuntimeOnly
.\setup_qwen.ps1 -ModelOnly
```

## Start the browser interface

```powershell
.\start_qwen.ps1
```

On the first run, `start_qwen.ps1` invokes setup automatically. Later runs go
directly to the local server. Use `-NoBrowser` or `-Port 18080` when needed.

If the browser does not open, visit `http://127.0.0.1:8080` after the terminal
reports that the model is loaded. Keep PowerShell open; press `Ctrl+C` to stop.

## What it does not do

The local browser is a chat interface. It does not automatically receive file,
terminal, GitHub, or operating-system permissions.
