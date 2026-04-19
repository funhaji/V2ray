import os
import sys
import platform
import subprocess
from pathlib import Path
from typing import Optional, List

# ── ANSI colours ──────────────────────────────────────────────────────────────
def supports_color() -> bool:
    try:
        return sys.stdout.isatty() and (
            platform.system() != "Windows"
            or "ANSICON" in os.environ
            or "WT_SESSION" in os.environ  # Windows Terminal
            or os.environ.get("TERM_PROGRAM") == "vscode"
        )
    except Exception:
        return False

USE_COLOR = supports_color()
RESET  = "\033[0m"  if USE_COLOR else ""
BOLD   = "\033[1m"  if USE_COLOR else ""
GREEN  = "\033[92m" if USE_COLOR else ""
CYAN   = "\033[96m" if USE_COLOR else ""
YELLOW = "\033[93m" if USE_COLOR else ""
RED    = "\033[91m" if USE_COLOR else ""

def info(msg):    print(f"{CYAN}[INFO]{RESET}  {msg}")
def success(msg): print(f"{GREEN}[OK]{RESET}    {msg}")
def warn(msg):    print(f"{YELLOW}[WARN]{RESET}  {msg}")
def error(msg):   print(f"{RED}[ERROR]{RESET} {msg}")
def header(msg):  print(f"\n{BOLD}{CYAN}{'─'*50}\n  {msg}\n{'─'*50}{RESET}")

# ── Helpers ───────────────────────────────────────────────────────────────────
OS = platform.system()  # "Windows" | "Darwin" | "Linux"

def pause_exit(code: int = 0):
    """Keep the window open before exiting (important when double-clicked)."""
    print()
    input("  Press Enter to close...")
    sys.exit(code)

def clean_path(raw: str) -> str:
    return raw.strip().strip('"').strip("'")

def ask_path(prompt: str, must_contain: str = None) -> Path:
    while True:
        raw = input(f"{BOLD}{prompt}{RESET} ").strip()
        if not raw:
            warn("No path entered. Try again.")
            continue
        p = Path(clean_path(raw))
        if not p.exists():
            error(f"Path not found: {p}")
            continue
        if not p.is_dir():
            error(f"That's a file, not a folder: {p}")
            continue
        if must_contain and not (p / must_contain).exists():
            warn(f"Couldn't find '{must_contain}' inside {p}.")
            warn("Are you sure this is the right folder?")
            choice = input("  Use it anyway? [y/N] ").strip().lower()
            if choice != "y":
                continue
        return p

def find_java_binary(jdk_path: Path) -> Optional[Path]:
    exe = "java.exe" if OS == "Windows" else "java"
    candidates = [jdk_path / "bin" / exe, jdk_path / exe]
    return next((c for c in candidates if c.exists()), None)

def get_java_version(java_bin: Path) -> str:
    try:
        result = subprocess.run(
            [str(java_bin), "-version"],
            capture_output=True, text=True, timeout=5
        )
        return (result.stderr or result.stdout).splitlines()[0]
    except Exception:
        return "unknown"

def detect_javafx_modules(javafx_lib: Path) -> List[str]:
    keywords = ["controls", "fxml", "graphics", "media", "swing", "web", "base"]
    found = []
    try:
        jars = [f.name for f in javafx_lib.glob("*.jar")]
    except Exception:
        jars = []
    for kw in keywords:
        if any(kw in jar for jar in jars):
            found.append(f"javafx.{kw}")
    return found if found else ["javafx.controls", "javafx.fxml"]

def write_run_script(javafx_lib: Path, modules: List[str],
                     main_class: str, classpath: str, output_dir: Path):
    mod_str = ",".join(modules)
    cp_flag = f'--class-path "{classpath}"' if classpath else ""

    if OS == "Windows":
        script = output_dir / "run_app.bat"
        script.write_text(
            "@echo off\n"
            f'java --module-path "{javafx_lib}" --add-modules {mod_str} '
            f'{cp_flag} {main_class}\n'
            "pause\n",
            encoding="utf-8"
        )
    else:
        script = output_dir / "run_app.sh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            f'java --module-path "{javafx_lib}" --add-modules {mod_str} '
            f'{cp_flag} {main_class}\n',
            encoding="utf-8"
        )
        script.chmod(0o755)

    success(f"Run script saved to: {script}")

def set_env_windows(java_home: Path):
    try:
        subprocess.run(["setx", "JAVA_HOME", str(java_home)],
                       check=True, capture_output=True)
        subprocess.run(["setx", "PATH", r"%JAVA_HOME%\bin;%PATH%"],
                       check=True, capture_output=True)
        success("JAVA_HOME and PATH set (takes effect in new terminals).")
    except Exception:
        warn("Couldn't set env vars automatically. Run these manually:\n")
        print(f'    setx JAVA_HOME "{java_home}"')
        print(r'    setx PATH "%JAVA_HOME%\bin;%PATH%"')

def set_env_unix(java_home: Path):
    shell = os.environ.get("SHELL", "/bin/bash")
    profile = "~/.zshrc" if "zsh" in shell else "~/.bashrc"
    print(f"\n  Add these to {profile}:\n")
    print(f'    export JAVA_HOME="{java_home}"')
    print(f'    export PATH="$JAVA_HOME/bin:$PATH"\n')

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    header("JavaFX Environment Setup")
    print(f"  OS: {BOLD}{OS}{RESET}  |  Python: {BOLD}{sys.version.split()[0]}{RESET}\n")

    # 1. Paths ─────────────────────────────────────────────────────────────────
    jdk_path    = ask_path("JDK folder path:", must_contain="bin")
    javafx_path = ask_path("JavaFX SDK folder path:", must_contain="lib")
    javafx_lib  = javafx_path / "lib"

    # 2. Validate JDK ──────────────────────────────────────────────────────────
    header("Validating JDK")
    java_bin = find_java_binary(jdk_path)
    if java_bin:
        success(f"Found: {java_bin}")
        info(f"Version: {get_java_version(java_bin)}")
    else:
        warn("java binary not found — continuing anyway.")

    # 3. JavaFX modules ────────────────────────────────────────────────────────
    header("Detecting JavaFX Modules")
    modules = detect_javafx_modules(javafx_lib)
    success(f"Modules: {', '.join(modules)}")

    # 4. App details ───────────────────────────────────────────────────────────
    header("App Details  (press Enter to skip)")
    main_class = input(f"  {BOLD}Main class{RESET} (e.g. com.example.App): ").strip()
    if not main_class:
        main_class = "YourMainClass"
    classpath = clean_path(input(f"  {BOLD}Class-path{RESET} (e.g. out\\MyApp): ").strip())

    # 5. Summary ───────────────────────────────────────────────────────────────
    header("Configuration Summary")
    info(f"JAVA_HOME  = {jdk_path}")
    info(f"JavaFX lib = {javafx_lib}")
    info(f"Modules    = {', '.join(modules)}")
    info(f"Main class = {main_class}")
    if classpath:
        info(f"Class-path = {classpath}")

    # 6. Env vars ──────────────────────────────────────────────────────────────
    header("Environment Variables")
    apply = input("  Set JAVA_HOME now? [Y/n] ").strip().lower()
    if apply != "n":
        if OS == "Windows":
            set_env_windows(jdk_path)
        else:
            set_env_unix(jdk_path)

    # 7. Run script ────────────────────────────────────────────────────────────
    header("Generate Run Script")
    dest_raw = input(f"  Save script where? [{BOLD}current folder{RESET}]: ").strip()
    dest = Path(clean_path(dest_raw)) if dest_raw else Path.cwd()
    dest.mkdir(parents=True, exist_ok=True)
    write_run_script(javafx_lib, modules, main_class, classpath, dest)

    # 8. Final command ─────────────────────────────────────────────────────────
    header("Run Command")
    cp_flag = f'--class-path "{classpath}"' if classpath else ""
    cmd = (
        f'java --module-path "{javafx_lib}" '
        f'--add-modules {",".join(modules)} '
        f'{cp_flag} {main_class}'
    ).strip()
    print(f"\n  {YELLOW}{cmd}{RESET}")
    print(f"\n{GREEN}{BOLD}All done!{RESET}")

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Cancelled.{RESET}")
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
    finally:
        pause_exit()
                  
