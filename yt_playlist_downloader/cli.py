import os
from typing import Optional

from .config import DEFAULT_CONFIG, load_config, save_config
from .downloader import PlaylistDownloader
from .logger import get_logger


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

    downloader = PlaylistDownloader(logger=logger)
    downloader.download_playlist(
        playlist_url=playlist_url,
        download_dir=download_dir,
        cookies_path=cookies_path,
        last_videos_count=last_videos,
        max_quality_height=config.get("max_quality_height", DEFAULT_CONFIG["max_quality_height"]),
        archive_path=config.get("archive_path", DEFAULT_CONFIG["archive_path"]),
    )


def main() -> None:
    logger = get_logger("yt_playlist_downloader")
    config = load_config()

    menu = """\n=== Téléchargeur de playlist YouTube ===
1) Lancer le téléchargement
2) Configuration
    3) Quitter
    Choix: """

    try:
        while True:
            choice = input(menu).strip()
            if choice == "1":
                start_download_menu(config, logger)
            elif choice == "2":
                config = configure_menu(config, logger)
            elif choice == "3":
                print("Au revoir !")
                break
            else:
                print("Choix invalide, merci de réessayer.\n")
    except KeyboardInterrupt:
        print("\nFermeture demandée. À bientôt !")
        logger.info("Fermeture forcée par l'utilisateur via Ctrl+C")


if __name__ == "__main__":
    main()
