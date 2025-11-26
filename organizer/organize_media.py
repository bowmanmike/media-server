#!/usr/bin/env python
import os
import time
import shutil
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from guessit import guessit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

DOWNLOADS_DIR = Path(os.environ.get("DOWNLOADS_DIR", "/downloads/complete"))
MOVIES_DIR = Path(os.environ.get("MOVIES_DIR", "/media/movies"))
TV_DIR = Path(os.environ.get("TV_DIR", "/media/tv"))

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE = "https://api.themoviedb.org/3"

# Ignore tiny files (< ~50MB) – likely samples
MIN_SIZE_BYTES = 50 * 1024 * 1024
SLEEP_SECONDS = int(os.environ.get("SLEEP_SECONDS", "300"))  # 5 min default

class TriggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # we’ll use POST /scan-once
        if self.path == "/scan-once":
            logging.info("HTTP trigger received: running sweep_once()")
            try:
                sweep_once()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            except Exception as e:  # noqa: BLE001
                logging.exception("Error in sweep_once() from HTTP trigger: %s", e)
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"ERROR")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        # Silence default HTTP request logging
        return



def tmdb_search_movie(title: str, year: Optional[int]) -> Optional[Dict[str, Any]]:
  if not TMDB_API_KEY:
    return None
  params: Dict[str, Any] = {"api_key": TMDB_API_KEY, "query": title}
  if year:
    params["year"] = year
  r = requests.get(f"{TMDB_BASE}/search/movie", params=params, timeout=10)
  if not r.ok:
    return None
  data = r.json()
  results = data.get("results") or []
  if not results:
    return None
  best = results[0]
  release_date = best.get("release_date") or ""
  movie_year = None
  if release_date[:4].isdigit():
    movie_year = int(release_date[:4])
  elif year:
    movie_year = year
  return {
    "title": best.get("title") or title,
    "year": movie_year,
  }


def tmdb_search_tv(title: str) -> Optional[Dict[str, Any]]:
  if not TMDB_API_KEY:
    return None
  params = {"api_key": TMDB_API_KEY, "query": title}
  r = requests.get(f"{TMDB_BASE}/search/tv", params=params, timeout=10)
  if not r.ok:
    return None
  data = r.json()
  results = data.get("results") or []
  if not results:
    return None
  best = results[0]
  name = best.get("name") or title
  first_air = best.get("first_air_date") or ""
  year = int(first_air[:4]) if first_air[:4].isdigit() else None
  return {"name": name, "year": year}


def build_tag_suffix(info: Dict[str, Any]) -> str:
  """Build something like: [1080P WEB-DL H265] from guessit fields."""
  tags = []

  screen = info.get("screen_size")
  if screen:
    tags.append(str(screen).upper())

  source = info.get("source")
  if source:
    tags.append(str(source).upper())

  video = info.get("video_codec")
  if video:
    tags.append(str(video).upper())

  audio = info.get("audio_codec")
  if audio:
    tags.append(str(audio).upper())

  seen = set()
  uniq = []
  for t in tags:
    if t not in seen:
      uniq.append(t)
      seen.add(t)

  return f" [{' '.join(uniq)}]" if uniq else ""


def handle_episode(path: Path, info: Dict[str, Any]) -> None:
  title = info.get("title")
  season = info.get("season")
  episode = info.get("episode")

  if not title or season is None or episode is None:
    logging.info("Skipping episode (missing title/season/episode): %s", path)
    return

  show_name = title
  tmdb_info = tmdb_search_tv(title)
  if tmdb_info:
    show_name = tmdb_info["name"] or show_name

  tag_suffix = build_tag_suffix(info)

  season_dir = TV_DIR / show_name / f"Season {season:02d}"
  season_dir.mkdir(parents=True, exist_ok=True)

  new_name = f"{show_name} - S{season:02d}E{episode:02d}{tag_suffix}{path.suffix}"
  dest = season_dir / new_name

  logging.info("TV: %s -> %s", path, dest)
  shutil.move(str(path), str(dest))


def handle_movie(path: Path, info: Dict[str, Any]) -> None:
  title = info.get("title")
  year = info.get("year")

  if not title:
    logging.info("Skipping movie (missing title): %s", path)
    return

  tmdb_info = tmdb_search_movie(title, year)
  if tmdb_info:
    title = tmdb_info["title"] or title
    year = tmdb_info["year"] or year

  tag_suffix = build_tag_suffix(info)

  MOVIES_DIR.mkdir(parents=True, exist_ok=True)
  if year:
    base = f"{title} ({year})"
  else:
    base = title

  new_name = f"{base}{tag_suffix}{path.suffix}"
  dest = MOVIES_DIR / new_name

  logging.info("Movie: %s -> %s", path, dest)
  shutil.move(str(path), str(dest))


def process_file(path: Path) -> None:
  if not path.is_file():
    return
  if path.stat().st_size < MIN_SIZE_BYTES:
    logging.info("Skipping small file: %s", path)
    return

  info = guessit(path.name)
  logging.debug("Guessit for %s: %s", path.name, json.dumps(info, indent=2, default=str))

  kind = info.get("type")
  if kind == "episode":
    handle_episode(path, info)
  elif kind == "movie":
    handle_movie(path, info)
  else:
    logging.info("Unknown type (%s) for %s; skipping", kind, path)


def sweep_once() -> None:
  if not DOWNLOADS_DIR.exists():
    logging.warning("Downloads dir %s does not exist", DOWNLOADS_DIR)
    return

  for root, _, files in os.walk(DOWNLOADS_DIR):
    for name in files:
      path = Path(root) / name
      try:
        process_file(path)
      except Exception as e:  # noqa: BLE001
        logging.exception("Error processing %s: %s", path, e)


def main() -> None:
    import sys

    run_once = "--once" in sys.argv

    logging.info("Organizer starting. run_once=%s downloads_dir=%s", run_once, DOWNLOADS_DIR)

    if not TMDB_API_KEY:
        logging.warning("TMDB_API_KEY not set; using filename info only.")

    if run_once:
        sweep_once()
        return

    # Start HTTP trigger server in a background thread
    server = HTTPServer(("0.0.0.0", 8000), TriggerHandler)
    logging.info("HTTP trigger server listening on 0.0.0.0:8000")

    server.serve_forever()


if __name__ == "__main__":
  main()
