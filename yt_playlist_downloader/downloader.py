import os
import sys
from typing import Optional

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .logger import get_logger


def _format_eta(seconds: Optional[int]) -> str:
    if seconds is None:
        return "unknown"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes:d}m{secs:02d}s"
    return f"{secs:d}s"


class PlaylistDownloader:
    def __init__(self, logger=None) -> None:
        self.logger = logger or get_logger(__name__)

    def _progress_hook(self, data):
        status = data.get("status")
        if status == "downloading":
            title = data.get("info_dict", {}).get("title", "Unknown title")
            percent = data.get("_percent_str", "?").strip()
            speed = data.get("_speed_str", "?").strip()
            eta = _format_eta(data.get("eta"))
            sys.stdout.write(
                f"\r[DOWNLOADING] {title[:50]:50} | {percent} at {speed} | ETA {eta}"
            )
            sys.stdout.flush()
        elif status == "finished":
            sys.stdout.write("\n")
            filename = data.get("filename")
            self.logger.info("Finished downloading %s", filename)
            print(f"Completed: {os.path.basename(filename)}")
        elif status == "error":
            self.logger.error("Error during download: %s", data)
            print("Encountered an error. Check logs for details.")

    def _determine_range(
        self, playlist_url: str, cookies_path: Optional[str], last_videos_count: int
    ) -> tuple[int, Optional[int]]:
        if last_videos_count <= 0:
            self.logger.info(
                "Téléchargement de toute la playlist en commençant par les vidéos les plus récentes."
            )
            return 1, None

        extract_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
        }
        if cookies_path:
            extract_opts["cookiefile"] = cookies_path

        total_items: Optional[int] = None
        try:
            with YoutubeDL(extract_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
            total_items = len(info.get("entries", []) or [])
        except Exception as exc:
            self.logger.warning(
                "Impossible de déterminer la taille de la playlist (%s). Téléchargement des %s dernières vidéos demandées.",
                exc,
                last_videos_count,
            )

        if total_items is not None and total_items <= 0:
            self.logger.warning("La playlist ne contient aucune vidéo détectable.")
            return 1, None

        if total_items is None:
            limited_count = last_videos_count
        else:
            limited_count = min(last_videos_count, total_items)

        self.logger.info(
            "Téléchargement des %s vidéos les plus récentes (index 1 à %s en ordre inverse)",
            limited_count,
            limited_count if limited_count else "?",
        )
        return 1, limited_count if limited_count > 0 else None

    def download_playlist(
        self,
        playlist_url: str,
        download_dir: str,
        cookies_path: Optional[str] = None,
        last_videos_count: int = 0,
        max_quality_height: Optional[int] = None,
        archive_path: Optional[str] = None,
    ) -> None:
        os.makedirs(download_dir, exist_ok=True)
        playlist_start, playlist_end = self._determine_range(
            playlist_url, cookies_path, last_videos_count
        )

        resolved_archive = archive_path or os.path.join("logs", "download_archive.txt")
        archive_dir = os.path.dirname(resolved_archive)
        if archive_dir:
            os.makedirs(archive_dir, exist_ok=True)

        if max_quality_height and max_quality_height > 0:
            format_selector = (
                f"bestvideo[height<={max_quality_height}]+bestaudio/best[height<="
                f"{max_quality_height}]"
            )
        else:
            format_selector = "bestvideo+bestaudio/best"

        ydl_opts = {
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
            "ignoreerrors": True,
            "noplaylist": False,
            "yesplaylist": True,
            "playliststart": playlist_start,
            "playlistend": playlist_end,
            "playlistreverse": True,
            "retries": 10,
            "fragment_retries": 20,
            "socket_timeout": 30,
            "continuedl": True,
            "nopart": False,
            "concurrent_fragment_downloads": 1,
            "progress_hooks": [self._progress_hook],
            "trim_file_name": 200,
            "format": format_selector,
            "download_archive": resolved_archive,
            "nooverwrites": True,
        }

        if cookies_path:
            ydl_opts["cookiefile"] = cookies_path

        self.logger.info("Starting playlist download: %s", playlist_url)
        self.logger.info("Saving to: %s", os.path.abspath(download_dir))
        if cookies_path:
            self.logger.info("Using cookies file: %s", cookies_path)
        if resolved_archive:
            self.logger.info(
                "Les vidéos déjà présentes dans l'archive seront ignorées: %s",
                os.path.abspath(resolved_archive),
            )

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([playlist_url])
            print("\nAll downloads attempted. Review logs for details.")
        except DownloadError as exc:
            error_message = str(exc)
            if "n challenge solving failed" in error_message:
                self.logger.error(
                    "yt-dlp a rencontré un échec de résolution de challenge (EJS). "
                    "Installez un runtime JavaScript pris en charge (ex: Node.js) et "
                    "assurez-vous que les scripts EJS de yt-dlp sont disponibles. Détails: %s",
                    error_message,
                )
                print(
                    "Erreur de challenge YouTube. Installez un runtime JavaScript (ex: Node.js) "
                    "et le challenge solver EJS. Consultez les logs pour plus de détails."
                )
            else:
                self.logger.error("Erreur yt-dlp: %s", error_message)
                print("yt-dlp a rencontré une erreur. Consultez les logs pour plus de détails.")
        except Exception as exc:  # yt-dlp already handles most errors
            self.logger.exception("Unexpected error while downloading playlist: %s", exc)
            print("A critical error occurred. See logs/app.log for details.")
