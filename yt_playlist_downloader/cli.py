import os
import signal
import subprocess
import sys
import time
from typing import Optional

from .config import DEFAULT_CONFIG, load_config, save_config
from .downloader import PlaylistDownloader
from .logger import get_logger


BACKGROUND_PID_FILE = os.path.join("logs", "background.pid")


def _save_background_pid(pid: int) -> None:
    os.makedirs("logs", exist_ok=True)
    with open(BACKGROUND_PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(pid))


def _load_background_pid() -> Optional[int]:
    if not os.path.exists(BACKGROUND_PID_FILE):
        return None
    try:
        with open(BACKGROUND_PID_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def _clear_background_pid(expected_pid: Optional[int] = None) -> None:
    if not os.path.exists(BACKGROUND_PID_FILE):
        return
    if expected_pid is not None:
        try:
            with open(BACKGROUND_PID_FILE, "r", encoding="utf-8") as f:
                current_pid = int(f.read().strip())
            if current_pid != expected_pid:
                return
        except (ValueError, OSError):
            pass
    try:
        os.remove(BACKGROUND_PID_FILE)
    except OSError:
        pass


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def _prompt(text: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or (default or "")


def _prompt_int(text: str, default: int, min_value: int = 0) -> int:
    while True:
        raw = _prompt(text, str(default))
        try:
            value = int(raw)
            if value < min_value:
                print(f"Merci d'entrer un entier supérieur ou égal à {min_value}.")
                continue
            return value
        except ValueError:
            print("Invalid number. Please try again.")


def _prompt_yes_no(text: str, default: bool = True) -> bool:
    default_display = "o" if default else "n"
    while True:
        answer = input(f"{text} [o/n] ({default_display}): ").strip().lower()
        if not answer:
            return default
        if answer in {"o", "oui", "y", "yes"}:
            return True
        if answer in {"n", "non", "no"}:
            return False
        print("Veuillez répondre par o ou n.")


def _prompt_cookies_path(current_default: Optional[str]) -> Optional[str]:
    default_display = current_default or DEFAULT_CONFIG["cookies_path"]
    raw = input(
        f"Chemin vers cookies.txt (YouTube, taper 'aucun' pour ne pas utiliser) [{default_display}]: "
    ).strip()

    lowered = raw.lower()
    if lowered in {"aucun", "none", "no", "non"}:
        return None
    if raw == "":
        return default_display
    return raw


def configure_menu(config: dict, logger) -> dict:
    print("\n--- Configuration ---")
    download_dir = _prompt("Default dossier de téléchargement", config["download_dir"])
    cookies_path = _prompt_cookies_path(config.get("cookies_path"))

    max_quality_height = _prompt_int(
        "Qualité maximale désirée (hauteur en pixels, 0 pour la meilleure disponible)",
        config.get("max_quality_height", DEFAULT_CONFIG["max_quality_height"]),
        min_value=0,
    )

    config.update({
        "download_dir": download_dir or DEFAULT_CONFIG["download_dir"],
        "cookies_path": cookies_path,
        "max_quality_height": max_quality_height,
    })
    save_config(config)
    logger.info("Configuration mise à jour")
    print("Configuration sauvegardée.\n")
    return config


def start_download_menu(config: dict, logger) -> None:
    print("\n--- Lancer le téléchargement ---")
    playlist_url = _prompt("URL de la playlist YouTube")
    while not playlist_url:
        print("L'URL ne peut pas être vide.")
        playlist_url = _prompt("URL de la playlist YouTube")

    cookies_path: Optional[str] = _prompt_cookies_path(config.get("cookies_path"))
    if cookies_path:
        if not os.path.exists(cookies_path):
            print("Attention: le fichier cookies.txt n'existe pas. Le téléchargement peut échouer.")
        else:
            config["cookies_path"] = cookies_path
            save_config(config)
    else:
        config["cookies_path"] = None
        save_config(config)

    last_videos = _prompt_int(
        "Nombre des dernières vidéos à télécharger (0 = toute la playlist)",
        0,
        min_value=0,
    )

    download_dir = _prompt("Dossier de téléchargement", config.get("download_dir", "downloads"))
    if not download_dir:
        download_dir = DEFAULT_CONFIG["download_dir"]

    if _prompt_yes_no(
        "Exécuter le téléchargement en arrière-plan pour survivre à la fermeture de la session SSH?",
        default=True,
    ):
        _launch_background_download(
            playlist_url=playlist_url,
            download_dir=download_dir,
            cookies_path=cookies_path,
            last_videos_count=last_videos,
            max_quality_height=config.get("max_quality_height", DEFAULT_CONFIG["max_quality_height"]),
            archive_path=config.get("archive_path", DEFAULT_CONFIG["archive_path"]),
            logger=logger,
        )
    else:
        downloader = PlaylistDownloader(logger=logger)
        downloader.download_playlist(
            playlist_url=playlist_url,
            download_dir=download_dir,
            cookies_path=cookies_path,
            last_videos_count=last_videos,
            max_quality_height=config.get("max_quality_height", DEFAULT_CONFIG["max_quality_height"]),
            archive_path=config.get("archive_path", DEFAULT_CONFIG["archive_path"]),
        )


def _launch_background_download(
    playlist_url: str,
    download_dir: str,
    cookies_path: Optional[str],
    last_videos_count: int,
    max_quality_height: Optional[int],
    archive_path: Optional[str],
    logger,
) -> None:
    os.makedirs("logs", exist_ok=True)
    background_log = os.path.join("logs", "background.log")
    cmd = [
        sys.executable,
        "-m",
        "yt_playlist_downloader.worker",
        "--playlist-url",
        playlist_url,
        "--download-dir",
        download_dir,
        "--last-videos",
        str(last_videos_count),
        "--max-quality-height",
        str(max_quality_height if max_quality_height is not None else 0),
        "--archive-path",
        archive_path or DEFAULT_CONFIG["archive_path"],
    ]
    if cookies_path:
        cmd.extend(["--cookies-path", cookies_path])

    with open(background_log, "a", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

    _save_background_pid(proc.pid)

    logger.info(
        "Téléchargement lancé en arrière-plan (PID %s). Suivez les sorties dans %s.",
        proc.pid,
        os.path.abspath(background_log),
    )
    print(
        f"Téléchargement lancé en arrière-plan (PID {proc.pid}). "
        f"Consultez {background_log} pour le détail."
    )
    print(f"PID enregistré dans {BACKGROUND_PID_FILE} pour une éventuelle annulation.")

    print("\nSuivi en direct des progrès (Ctrl+C pour arrêter le suivi, le téléchargement continuera):")
    _stream_background_log(background_log, proc)


def _stream_background_log(log_path: str, process: subprocess.Popen) -> None:
    """Stream the background process log to stdout until it exits or user stops."""

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
            log_file.seek(0, os.SEEK_END)
            while True:
                line = log_file.readline()
                if line:
                    print(line, end="")
                else:
                    if process.poll() is not None:
                        # Process finished; print any remaining buffered lines then exit
                        remaining = log_file.read()
                        if remaining:
                            print(remaining, end="")
                        print("\nTéléchargement d'arrière-plan terminé.")
                        _clear_background_pid(expected_pid=process.pid)
                        break
                    time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nSuivi interrompu par l'utilisateur. Le téléchargement se poursuit en arrière-plan.")


def cancel_background_download(logger) -> None:
    print("\n--- Annuler un téléchargement en arrière-plan ---")
    saved_pid = _load_background_pid()
    default_display = str(saved_pid) if saved_pid else None
    raw_pid = _prompt("PID du téléchargement à annuler", default_display)
    if not raw_pid:
        print("Aucune action effectuée.\n")
        return

    try:
        pid = int(raw_pid)
    except ValueError:
        print("PID invalide. Merci de réessayer.\n")
        return

    if not _process_alive(pid):
        print(f"Aucun téléchargement en arrière-plan actif avec le PID {pid}.")
        _clear_background_pid(expected_pid=pid)
        return

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        print(f"Aucun téléchargement en arrière-plan actif avec le PID {pid}.")
    except PermissionError:
        print("Permission refusée pour annuler ce téléchargement.")
    else:
        logger.info("Téléchargement en arrière-plan (PID %s) annulé par l'utilisateur.", pid)
        print(f"Téléchargement en arrière-plan (PID {pid}) annulé.")
    finally:
        _clear_background_pid(expected_pid=pid)

    print("\nSuivi en direct des progrès (Ctrl+C pour arrêter le suivi, le téléchargement continuera):")
    _stream_background_log(background_log, proc)


def _stream_background_log(log_path: str, process: subprocess.Popen) -> None:
    """Stream the background process log to stdout until it exits or user stops."""

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
            log_file.seek(0, os.SEEK_END)
            while True:
                line = log_file.readline()
                if line:
                    print(line, end="")
                else:
                    if process.poll() is not None:
                        # Process finished; print any remaining buffered lines then exit
                        remaining = log_file.read()
                        if remaining:
                            print(remaining, end="")
                        print("\nTéléchargement d'arrière-plan terminé.")
                        break
                    time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nSuivi interrompu par l'utilisateur. Le téléchargement se poursuit en arrière-plan.")


def main() -> None:
    logger = get_logger("yt_playlist_downloader")
    config = load_config()

    menu = """\n=== Téléchargeur de playlist YouTube ===
1) Lancer le téléchargement
2) Configuration
3) Annuler un téléchargement en arrière-plan
4) Quitter
Choix: """

    try:
        while True:
            choice = input(menu).strip()
            if choice == "1":
                start_download_menu(config, logger)
            elif choice == "2":
                config = configure_menu(config, logger)
            elif choice == "3":
                cancel_background_download(logger)
            elif choice == "4":
                print("Au revoir !")
                break
            else:
                print("Choix invalide, merci de réessayer.\n")
    except KeyboardInterrupt:
        print("\nFermeture demandée. À bientôt !")
        logger.info("Fermeture forcée par l'utilisateur via Ctrl+C")


if __name__ == "__main__":
    main()
