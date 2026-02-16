import os
import sys
from typing import Any, Optional

from yt_dlp import YoutubeDL as _YoutubeDL
from yt_dlp.utils import DownloadError

from .logger import get_logger

YoutubeDL: Any = _YoutubeDL


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

    def _entry_to_video_url(self, entry: dict) -> Optional[str]:
        webpage_url = entry.get("webpage_url")
        if isinstance(webpage_url, str) and webpage_url.strip():
            return webpage_url.strip()

        url = entry.get("url")
        if isinstance(url, str) and url.strip():
            url = url.strip()
            if url.startswith("http://") or url.startswith("https://"):
                return url

        video_id = entry.get("id")
        if isinstance(video_id, str) and video_id.strip():
            return f"https://www.youtube.com/watch?v={video_id.strip()}"

        return None

    def export_playlist_txt(
        self,
        playlist_url: str,
        output_path: str,
        cookies_path: Optional[str] = None,
        last_videos_count: int = 0,
    ) -> int:
        playlist_start, playlist_end = self._determine_range(
            playlist_url,
            cookies_path,
            last_videos_count,
            operation="Export",
        )

        extract_opts: dict[str, Any] = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "playliststart": playlist_start,
            "playlistend": playlist_end,
            "playlistreverse": True,
        }
        if cookies_path:
            extract_opts["cookiefile"] = cookies_path

        self.logger.info("Export playlist URLs to: %s", os.path.abspath(output_path))

        try:
            with YoutubeDL(extract_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
        except Exception as exc:
            self.logger.exception("Impossible d'extraire la playlist pour export: %s", exc)
            raise

        entries = info.get("entries", []) or []
        urls: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            resolved = self._entry_to_video_url(entry)
            if resolved:
                urls.append(resolved)

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for url in urls:
                f.write(url)
                f.write("\n")

        self.logger.info("Playlist export written: %s URLs", len(urls))
        return len(urls)

    def download_playlist_txt(
        self,
        playlist_txt_path: str,
        download_dir: str,
        cookies_path: Optional[str] = None,
        last_videos_count: int = 0,
        max_quality_height: Optional[int] = None,
        archive_path: Optional[str] = None,
    ) -> None:
        try:
            with open(playlist_txt_path, "r", encoding="utf-8") as f:
                raw_lines = f.readlines()
        except OSError as exc:
            self.logger.error("Impossible de lire %s: %s", playlist_txt_path, exc)
            raise

        urls: list[str] = []
        for raw in raw_lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)

        if not urls:
            self.logger.warning("Aucune URL trouvée dans %s", playlist_txt_path)
            print("Aucune URL à télécharger (playlist.txt vide).")
            return

        if last_videos_count and last_videos_count > 0:
            urls = urls[-last_videos_count:]

        os.makedirs(download_dir, exist_ok=True)

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
            "noplaylist": True,
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

        self.logger.info("Starting download from playlist.txt: %s", playlist_txt_path)
        self.logger.info("URLs to download: %s", len(urls))
        self.logger.info("Saving to: %s", os.path.abspath(download_dir))

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download(urls)
            print("\nAll downloads attempted. Review logs for details.")
        except DownloadError as exc:
            self.logger.error("Erreur yt-dlp: %s", str(exc))
            print("yt-dlp a rencontré une erreur. Consultez les logs pour plus de détails.")
        except Exception as exc:
            self.logger.exception("Unexpected error while downloading from playlist.txt: %s", exc)
            print("A critical error occurred. See logs/app.log for details.")

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
        self,
        playlist_url: str,
        cookies_path: Optional[str],
        last_videos_count: int,
        operation: str = "Téléchargement",
    ) -> tuple[int, Optional[int]]:
        if last_videos_count <= 0:
            self.logger.info(
                "%s de toute la playlist en commençant par les vidéos les plus récentes.",
                operation,
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
            "%s des %s vidéos les plus récentes (index 1 à %s en ordre inverse)",
            operation,
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
            playlist_url,
            cookies_path,
            last_videos_count,
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

            lowered = error_message.lower()
            is_youtube_challenge = (
                "challenge" in lowered
                and (
                    "solving failed" in lowered
                    or "ejs" in lowered
                    or "javascript" in lowered
                    or "js runtime" in lowered
                    or "external javascript" in lowered
                )
            )

            if is_youtube_challenge:
                self.logger.error(
                    "yt-dlp a rencontré un échec de résolution de challenge (EJS). "
                    "Assurez-vous que Node.js et Deno sont installes, puis mettez a jour yt-dlp "
                    "(pip install -U 'yt-dlp[default]'). Details: %s",
                    error_message,
                )
                print(
                    "Erreur de challenge YouTube (EJS). Installez Node.js et Deno, puis mettez a jour yt-dlp "
                    "(pip install -U 'yt-dlp[default]'). Consultez les logs pour plus de details."
                )
            else:
                self.logger.error("Erreur yt-dlp: %s", error_message)
                print("yt-dlp a rencontré une erreur. Consultez les logs pour plus de détails.")
        except Exception as exc:  # yt-dlp already handles most errors
            self.logger.exception("Unexpected error while downloading playlist: %s", exc)
            print("A critical error occurred. See logs/app.log for details.")
