import argparse
import os
import shutil
from typing import Optional

from .downloader import PlaylistDownloader
from .logger import get_logger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Télécharger une playlist YouTube en tâche de fond",
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--playlist-url")
    source.add_argument(
        "--playlist-txt-input",
        default=None,
        help="Chemin vers un fichier texte (1 URL par ligne) à télécharger.",
    )
    parser.add_argument("--download-dir", required=True)
    parser.add_argument("--cookies-path", default=None)
    parser.add_argument("--last-videos", type=int, default=0)
    parser.add_argument("--max-quality-height", type=int, default=0)
    parser.add_argument("--archive-path", default=None)
    parser.add_argument(
        "--export-playlist-txt",
        action="store_true",
        help="Exporte la playlist dans un fichier texte (1 URL par ligne) au lieu de télécharger les vidéos.",
    )
    parser.add_argument(
        "--playlist-txt-path",
        default=None,
        help="Chemin du fichier playlist.txt (par défaut: <download-dir>/playlist.txt).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    missing: list[str] = []
    if shutil.which("node") is None:
        missing.append("node")
    if shutil.which("deno") is None:
        missing.append("deno")
    if missing:
        print(
            "[INFO] Runtime JavaScript manquant pour YouTube (EJS): "
            f"{', '.join(missing)}."
        )
    logger = get_logger("yt_playlist_downloader.worker")
    downloader = PlaylistDownloader(logger=logger)

    if args.export_playlist_txt and args.playlist_txt_input:
        raise SystemExit("--export-playlist-txt n'est pas compatible avec --playlist-txt-input")

    if args.export_playlist_txt:
        output_path = args.playlist_txt_path or os.path.join(args.download_dir, "playlist.txt")
        count = downloader.export_playlist_txt(
            playlist_url=args.playlist_url,
            output_path=output_path,
            cookies_path=args.cookies_path,
            last_videos_count=args.last_videos,
        )
        print(f"playlist.txt écrit: {output_path} ({count} URLs)")
        return

    if args.playlist_txt_input:
        max_height: Optional[int] = args.max_quality_height or None
        downloader.download_playlist_txt(
            playlist_txt_path=args.playlist_txt_input,
            download_dir=args.download_dir,
            cookies_path=args.cookies_path,
            last_videos_count=args.last_videos,
            max_quality_height=max_height,
            archive_path=args.archive_path,
        )
        return

    max_height: Optional[int] = args.max_quality_height or None
    downloader.download_playlist(
        playlist_url=args.playlist_url,
        download_dir=args.download_dir,
        cookies_path=args.cookies_path,
        last_videos_count=args.last_videos,
        max_quality_height=max_height,
        archive_path=args.archive_path,
    )


if __name__ == "__main__":
    main()
