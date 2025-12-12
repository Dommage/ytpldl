import argparse
from typing import Optional

from .downloader import PlaylistDownloader
from .logger import get_logger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Télécharger une playlist YouTube en tâche de fond",
    )
    parser.add_argument("--playlist-url", required=True)
    parser.add_argument("--download-dir", required=True)
    parser.add_argument("--cookies-path", default=None)
    parser.add_argument("--last-videos", type=int, default=0)
    parser.add_argument("--max-quality-height", type=int, default=0)
    parser.add_argument("--archive-path", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    logger = get_logger("yt_playlist_downloader.worker")
    downloader = PlaylistDownloader(logger=logger)
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
