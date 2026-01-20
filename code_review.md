# Code Review

**Date:** 2026-01-20
**Project:** yt_playlist_downloader
**Repository:** ytpldl
**Python Version:** 3.13.9
**Platform:** Windows (Code is Linux-specific - see Critical Issues)

---

## Executive Summary

Well-structured CLI application for YouTube playlist downloads with good separation of concerns. However, **critical platform compatibility issues** prevent it from running on Windows. The code is designed exclusively for Linux/Unix environments and will fail completely on the current development environment.

**Overall Grade:** ⚠️ **Needs Critical Fixes Before Use**

---

## 🔴 CRITICAL Issues

### 1. Platform Incompatibility - Code Won't Work on Windows

**Location:** `cli.py` lines 66, 247, 319

**Issue:** Code uses Linux-specific APIs that don't exist on Windows:

```python
# Line 66 - Linux-only filesystem
cmdline_path = f"/proc/{pid}/cmdline"

# Line 247 - Unix-only subprocess parameter
start_new_session=True,

# Line 319 - Unix-only signal function
os.killpg(pid, signal.SIGTERM)
```

**Impact:**
- Background process detection (`_is_download_process`) will fail
- Background download launching will fail
- Background download cancellation will fail
- Application will crash or behave incorrectly on Windows

**Recommended Fix:**

```python
import platform
import psutil  # Add to requirements.txt

def _is_download_process(pid: int) -> bool:
    """Check if a PID corresponds to an active download process."""

    if not _process_alive(pid):
        return False

    if platform.system() == "Linux":
        cmdline_path = f"/proc/{pid}/cmdline"
        try:
            with open(cmdline_path, "rb") as cmd_file:
                content = cmd_file.read().decode(errors="ignore")
        except OSError:
            return False
        parts = content.split("\0")
        return any("yt_playlist_downloader.worker" in part for part in parts)

    elif platform.system() == "Windows":
        try:
            process = psutil.Process(pid)
            return "yt_playlist_downloader.worker" in " ".join(process.cmdline())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    return False

def _launch_background_download(...):
    # ...

    # Platform-specific subprocess configuration
    if platform.system() == "Windows":
        # Windows: Use CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    else:
        # Unix: Use start_new_session
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
```

**For termination:**

```python
def cancel_background_download(logger) -> None:
    # ...
    try:
        if platform.system() == "Windows":
            # Windows: Terminate specific process
            os.kill(pid, signal.SIGTERM)
        else:
            # Unix: Kill process group
            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        print(f"No active background download with PID {pid}.")
    except PermissionError:
        print("Permission denied to cancel this download.")
```

**Update `requirements.txt`:**
```
psutil>=5.9.0
```

---

### 2. Broad Exception Handling - Can Hide Bugs

**Location:** `downloader.py` lines 69, 173

**Issue:** Catching all `Exception` types makes debugging difficult and can mask serious issues.

```python
# Line 69
except Exception as exc:
    self.logger.warning(...)

# Line 173
except Exception as exc:
    self.logger.exception(...)
```

**Impact:**
- Harder to debug when unexpected exceptions occur
- Type errors, import errors, etc. are silently caught
- Makes code behavior unpredictable

**Recommended Fix:**

```python
# For playlist extraction (line 66-74)
try:
    with YoutubeDL(extract_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
    total_items = len(info.get("entries", []) or [])
except (DownloadError, KeyError, TypeError, ValueError) as exc:
    self.logger.warning(
        "Unable to determine playlist size (%s). Downloading %s most recent videos.",
        exc,
        last_videos_count,
    )
except Exception as exc:
    self.logger.error("Unexpected error while extracting playlist info: %s", exc)
    raise

# For download execution (line 173)
except DownloadError as exc:
    error_message = str(exc)
    # Handle specific YouTube challenge errors
    if "challenge solving failed" in error_message:
        self.logger.error(...)
        print(...)
    else:
        self.logger.error("yt-dlp error: %s", error_message)
        print(...)
except (OSError, PermissionError) as exc:
    self.logger.error("File system error: %s", exc)
    print("File system error. Check download directory permissions.")
except Exception as exc:
    self.logger.exception("Unexpected error while downloading playlist: %s", exc)
    print("A critical error occurred. See logs/app.log for details.")
```

---

## ⚠️ Important Issues

### 3. Process Termination Logic Flaw

**Location:** `cli.py` line 319

**Issue:** You're saving a single PID but using `os.killpg()` which kills the **entire process group**, potentially killing unrelated processes.

```python
os.killpg(pid, signal.SIGTERM)  # Kills entire process group!
```

**Impact:**
- Could kill other unrelated processes that happen to be in the same process group
- Security and stability risk
- Unintended side effects

**Recommended Fix:**

```python
def cancel_background_download(logger) -> None:
    # ... (existing code up to line 318)

    try:
        if platform.system() == "Windows":
            # Windows: Terminate specific process
            os.kill(pid, signal.SIGTERM)
        else:
            # Unix: Kill process group OR specific process
            # Option 1: Kill just the specific process
            os.kill(pid, signal.SIGTERM)
            # Option 2: Kill process group (more aggressive)
            # os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        print(f"No active background download with PID {pid}.")
    except PermissionError:
        print("Permission denied to cancel this download.")
    else:
        logger.info("Background download (PID %s) canceled by user.", pid)
        print(f"Background download (PID {pid}) canceled.")
    finally:
        _clear_background_pid(expected_pid=pid)
```

---

### 4. Hardcoded Log Level - Not Configurable

**Location:** `logger.py` line 14

**Issue:** Log level is hardcoded to `INFO` and cannot be changed without modifying code.

```python
logger.setLevel(logging.INFO)  # Cannot be changed
```

**Impact:**
- Cannot debug issues with DEBUG level logs
- Cannot reduce verbosity in production
- Inflexible for different environments

**Recommended Fix:**

```python
import os

def get_logger(name: Optional[str] = None, log_level: Optional[str] = None) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name or "yt_playlist_downloader")

    if not logger.handlers:
        # Allow log level override via environment variable
        level_str = log_level or os.environ.get("YT_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_str, logging.INFO)
        logger.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.FileHandler(LOG_PATH)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        logger.propagate = False
    return logger
```

**Usage:**
```bash
# Set debug level via environment
export YT_LOG_LEVEL=DEBUG
python main.py
```

---

### 5. Permission Error Handling Inaccurate

**Location:** `cli.py` lines 51-57

**Issue:** Returning `True` on `PermissionError` is misleading. The process might not exist, just inaccessible.

```python
except PermissionError:
    return True  # Assumes process is alive - misleading!
```

**Impact:**
- May incorrectly assume process is alive when it's not
- Could lead to stale PID tracking
- Unpredictable behavior in cancel_download

**Recommended Fix:**

```python
def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        # Process doesn't exist
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        logger.warning(f"No permission to signal process {pid}, assuming it's alive")
        return True
    except OSError:
        # Other OS errors - assume not alive
        return False
    else:
        # No exception means process exists and is accessible
        return True
```

---

## 📝 Code Quality Issues

### 6. Type Hints Incomplete

**Issue:** Several functions missing return type hints.

**Locations:**
- `cli.py`: `_prompt()` (line 89), `_process_alive()` (line 49)
- `cli.py`: `_active_download_pids()` (line 77)
- `downloader.py`: `_format_eta()` (line 11) - has hint but could be explicit

**Recommended Fix:**

```python
def _prompt(text: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or (default or "")

def _process_alive(pid: int) -> bool:
    # ... existing code
    pass

def _active_download_pids() -> list[int]:
    """Return list of active background download PIDs."""
    active_pids: list[int] = []
    saved_pid = _load_background_pid()
    if saved_pid and _is_download_process(saved_pid):
        active_pids.append(saved_pid)
    elif saved_pid:
        _clear_background_pid(expected_pid=saved_pid)
    return active_pids
```

---

### 7. Language Inconsistency

**Issue:** Mixing French and English in the codebase.

**Examples:**
- CLI user prompts: French (`"URL de la playlist YouTube"`)
- Log messages: Mixed English (`"Starting playlist download"` vs `"Téléchargement de toute la playlist"`)
- README: French
- Variable names: English (good practice)

**Recommendation:**

**Option A - Standardize to English** (Recommended for code):
- User-facing messages can remain French
- All log messages, comments, docstrings should be English
- This makes the codebase easier for international collaboration

**Option B - Standardize to French:**
- Everything in French
- Better if this is a French-only project

**Example English logging:**

```python
# downloader.py line 52-53 (currently French)
self.logger.info(
    "Downloading entire playlist, starting from most recent videos."
)
```

---

### 8. Missing Docstrings

**Issue:** `logger.py` lacks docstrings explaining implementation details.

**Questions that should be answered:**
- Why is `logger.propagate = False` set?
- When are file_handler vs stream_handler used?
- Why is the logger not re-initialized if handlers exist?

**Recommended Fix:**

```python
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get or create a configured logger instance.

    The logger is configured with both file and stream handlers. File logs
    are always written to LOG_PATH. Stream logs are written to console.

    Important notes:
    - logger.propagate is set to False to prevent duplicate log messages
    - Handlers are only added once to prevent duplicate logs on repeated calls
    - The same logger instance is returned for the same name (Python's singleton pattern)

    Args:
        name: Logger name. If None, uses "yt_playlist_downloader"

    Returns:
        Configured logging.Logger instance
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name or "yt_playlist_downloader")
    if not logger.handlers:
        # ... existing code
    return logger
```

---

## 📋 Minor Issues

### 9. Error String Typo

**Location:** `downloader.py` line 159

**Issue:** Searching for `"n challenge"` which seems like a typo.

```python
if "n challenge solving failed" in error_message:
```

**Recommended Fix:**

```python
if "challenge solving failed" in error_message:
    # OR
if "an challenge" in error_message or "challenge solving failed" in error_message:
```

---

### 10. README vs Code Mismatch

**Issue:** README shows different menu options than the code.

**README shows:**
```
1) Lancer le téléchargement
2) Configuration
3) Quitter
```

**Code actually has (cli.py line 335-340):**
```
1) Lancer le téléchargement
2) Configuration
3) Annuler un téléchargement en arrière-plan  # Missing from README
4) Quitter
```

**Recommended Fix:**

Update README.md menu section to match actual implementation.

---

## ✅ What's Good

### 1. Clean Architecture
Excellent separation of concerns:
- `cli.py` - User interface and menu logic
- `downloader.py` - Download business logic
- `config.py` - Configuration management
- `logger.py` - Logging setup
- `worker.py` - Background task entry point

### 2. Type Hints Used
Good practice of using type hints throughout, though incomplete.

### 3. Proper Error Logging
Exceptions are logged with context, making debugging easier.

### 4. Input Validation
Good user input handling with prompts and validation loops.

### 5. Archive Tracking
Uses `download_archive.txt` to prevent re-downloading existing files.

### 6. Cookie Support
Properly handles private playlists via cookie files.

### 7. Progress Hooks
Real-time download progress displayed to user.

### 8. Background Process Support
Allows downloads to continue after SSH session closes (on Unix).

---

## 🎯 Recommended Action Plan

### Priority 1 (Fix Immediately - Showstoppers)

1. **Add platform detection and Windows support**
   - Detect OS with `platform.system()`
   - Implement Windows alternatives for `/proc/`, `start_new_session`, `os.killpg`
   - Use `psutil` for cross-platform process management
   - Update `requirements.txt` with `psutil>=5.9.0`

2. **Fix `os.killpg()` to use appropriate termination method**
   - Windows: `os.kill(pid, signal.SIGTERM)`
   - Unix: `os.kill(pid, signal.SIGTERM)` or `os.killpg(os.getpgid(pid), signal.SIGTERM)`

3. **Replace `/proc/` logic with cross-platform alternative**
   - Use `psutil.Process(pid).cmdline()` for Windows
   - Keep `/proc/` for Linux

### Priority 2 (Improve Reliability)

4. **Narrow exception handling in downloader.py**
   - Catch specific exceptions: `DownloadError`, `KeyError`, `TypeError`, `ValueError`, `OSError`, `PermissionError`
   - Keep general `Exception` as last resort with re-raise or detailed logging

5. **Make log level configurable**
   - Read from environment variable `YT_LOG_LEVEL`
   - Add parameter to `get_logger()`

6. **Fix permission error handling logic**
   - Log warning but clarify assumption
   - Document behavior

### Priority 3 (Code Quality)

7. **Complete type hints**
   - Add return types to all functions
   - Use more specific types where appropriate

8. **Standardize language**
   - Decide on English or French
   - Apply consistently across codebase

9. **Add missing docstrings**
   - Document all public functions
   - Explain implementation details

10. **Update README**
    - Add option 3 (Cancel background download)
    - Match actual menu implementation

11. **Fix error string typo**
    - Correct `"n challenge"` search term

### Priority 4 (Additions)

12. **Add tests**
    - Unit tests for each module
    - Integration tests for download flow
    - Mock `yt-dlp` in tests

13. **Add `.gitignore`**
    ```
    __pycache__/
    *.py[cod]
    logs/
    config/config.json
    cookies.txt
    *.log
    .venv/
    .env
    ```

14. **Add configuration validation**
    - Verify `download_dir` is writable
    - Verify `cookies_path` exists if specified
    - Validate URL format

15. **Add signal handlers for graceful shutdown**
    - Handle `SIGTERM`, `SIGINT` gracefully
    - Cleanup resources before exit

---

## 🔍 Additional Suggestions

### 1. Consider Using `subprocess.run()` for Background Tasks

`subprocess.run()` provides a higher-level interface with better defaults:

```python
# Current approach (line 243-250)
proc = subprocess.Popen(cmd, ...)

# Alternative approach (for simpler use cases)
# Note: This might require changes to your streaming logic
result = subprocess.run(cmd, capture_output=True, text=True)
```

However, since you need to stream logs and track the PID, `Popen()` is appropriate here.

### 2. Add Version Information

Track application version for debugging and updates:

```python
__version__ = "1.0.0"
```

Add to `__init__.py` and display in help text or logs.

### 3. Add Progress Bar

Consider using `tqdm` for a nicer progress display:

```python
from tqdm import tqdm

# In progress_hook
with tqdm(total=100, desc="Downloading") as pbar:
    # Update progress
```

### 4. Add Maximum Retries Configuration

Currently hardcoded (retries=10, fragment_retries=20). Make configurable:

```python
# config.py
DEFAULT_CONFIG = {
    # ...
    "retries": 10,
    "fragment_retries": 20,
    "socket_timeout": 30,
}
```

### 5. Add Download Speed Limit

Allow users to limit download bandwidth:

```python
# In ydl_opts
ydl_opts["ratelimit"] = max_speed  # bytes per second
```

---

## 📊 Metrics

- **Total Python Files:** 7
- **Total Lines of Code:** ~650
- **Test Files:** 0
- **Type Coverage:** ~80%
- **Docstring Coverage:** ~20%
- **Platform Support:** Linux-only (⚠️ Critical)
- **Dependencies:** 2 (yt-dlp, js2py)

---

## Conclusion

This is a well-structured application with good separation of concerns and thoughtful features. However, the **critical platform incompatibility** must be addressed before the code can be used on Windows. The code follows good practices in many areas but would benefit from:

1. **Cross-platform compatibility** (critical blocker)
2. **More specific exception handling**
3. **Completed type hints**
4. **Test coverage**
5. **Better documentation**

With these improvements, this would be a production-ready application.

**Next Steps:**
1. Fix platform compatibility issues (Priority 1)
2. Add basic tests
3. Improve exception handling
4. Consider adding to CI/CD pipeline for automated testing
