# -*- coding: utf-8 -*-
"""
generator/video_mockup.py — 비디오 목업 스텁 (미구현).

generate_all_mockups()가 00번 MP4 목업 슬롯 생성을 위해 import 시도.
실제 구현 전까지 False를 반환하는 스텁으로 WARNING 없이 건너뜀.
"""

# 니치/카테고리별 특성 데이터 (미구현 — 빈 dict)
CATEGORY_FEATURES: dict = {}


def generate_video_mockup(
    art_path: str,
    output_path: str,
    category_features: dict | None = None,
    page_paths: list | None = None,
) -> bool:
    """MP4 목업 생성 스텁. 미구현 — 항상 False 반환."""
    return False
