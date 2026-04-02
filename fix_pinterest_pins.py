# -*- coding: utf-8 -*-
"""
fix_pinterest_pins.py — 발행됐지만 핀 누락된 리스팅 Pinterest 핀 복구.

실행:
    python fix_pinterest_pins.py
"""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent


def _get_listing_image_url(listing_id: str) -> str | None:
    """Etsy API로 리스팅 대표 이미지 URL 조회."""
    try:
        from publisher.etsy_api import _api_request
        result = _api_request("GET", f"/application/listings/{listing_id}/images")
        if not result:
            return None
        images = result.get("results", [])
        if not images:
            return None
        # rank=1 이미지 우선
        images.sort(key=lambda x: x.get("rank", 99))
        url = images[0].get("url_fullxfull") or images[0].get("url_570xN")
        return url
    except Exception as e:
        logger.error("이미지 URL 조회 실패 listing=%s: %s", listing_id, e)
        return None


def _download_image(url: str, dest: Path) -> bool:
    """이미지 URL → 로컬 파일 다운로드."""
    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        logger.info("이미지 다운로드 완료: %s", dest.name)
        return True
    except Exception as e:
        logger.error("이미지 다운로드 실패: %s", e)
        return False


def run():
    queue_path = _BASE_DIR / "publish_queue.json"
    pins_path  = _BASE_DIR / "db" / "pinterest_pins.json"

    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    pins  = json.loads(pins_path.read_text(encoding="utf-8")) if pins_path.exists() else {"pins": {}, "daily": {}}
    pinned_ids = set(pins.get("pins", {}).keys())

    # 핀 누락된 항목만 추출
    pending = [
        e for e in queue
        if e.get("done") and e.get("pinterest_info") and str(e["listing_id"]) not in pinned_ids
    ]

    if not pending:
        logger.info("핀 누락 항목 없음 — 완료")
        return

    logger.info("핀 누락 항목: %d개", len(pending))

    from publisher.pinterest import pin_listing

    with tempfile.TemporaryDirectory() as tmpdir:
        for entry in pending:
            listing_id = str(entry["listing_id"])
            info = entry["pinterest_info"]

            logger.info("처리 중: listing_id=%s (%s)", listing_id, info.get("title", "")[:50])

            # Etsy에서 이미지 URL 조회
            img_url = _get_listing_image_url(listing_id)
            if not img_url:
                logger.warning("이미지 URL 없음 — 스킵: %s", listing_id)
                continue

            # 이미지 다운로드
            img_path = Path(tmpdir) / f"{listing_id}.jpg"
            if not _download_image(img_url, img_path):
                continue

            # Pinterest 핀 생성
            etsy_url = f"https://www.etsy.com/listing/{listing_id}"
            result = pin_listing(
                listing_id    = listing_id,
                listing_title = info.get("title", "Digital Planner Printable"),
                image_path    = str(img_path),
                etsy_url      = etsy_url,
                niche         = info.get("niche"),
                seo_tags      = info.get("tags"),
            )
            status = result.get("status", "error")
            if status == "success":
                logger.info("핀 완료: listing_id=%s pin_id=%s", listing_id, result.get("pin_id"))
            elif status == "duplicate":
                logger.info("이미 핀 있음: listing_id=%s", listing_id)
            else:
                logger.warning("핀 실패: listing_id=%s status=%s", listing_id, status)


if __name__ == "__main__":
    run()
