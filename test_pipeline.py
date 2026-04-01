# -*- coding: utf-8 -*-
"""
플래너 파이프라인 로컬 테스트 -- Etsy 업로드 없음.

테스트 순서:
  1. 플래너 생성 (HTML → PDF)
  2. 목업 10장 생성
  3. SEO (제목 + 태그 + 설명) LLM 실호출
  4. 채점 결과 출력
  5. output/test_XXXX/ 폴더에 전체 파일 저장

실행:
    python test_pipeline.py                                      # 기본 (daily × sage_green)
    python test_pipeline.py --planner-type weekly                # 타입 지정
    python test_pipeline.py --planner-niche ADHD                 # 니치 지정
    python test_pipeline.py --mock                               # 이미지 API 없이 테스트
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# ── 로그 설정 ──
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(log_file), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("test_pipeline")

# ── sys.path ──
sys.path.insert(0, str(Path(__file__).parent))


# ══════════════════════════════════════════════
# 헬퍼
# ══════════════════════════════════════════════

def _sep(label: str):
    logger.info("")
    logger.info("=" * 60)
    logger.info("  %s", label)
    logger.info("=" * 60)


def _check(cond: bool, msg: str) -> bool:
    if cond:
        logger.info("  PASS  %s", msg)
    else:
        logger.error("  FAIL  %s", msg)
    return cond


def _fmt_size(path: str) -> str:
    try:
        sz = Path(path).stat().st_size
        if sz > 1024 * 1024:
            return f"{sz/1024/1024:.1f}MB"
        return f"{sz/1024:.0f}KB"
    except Exception:
        return "?"


# ══════════════════════════════════════════════
# 1. 상품 생성
# ══════════════════════════════════════════════

def test_generate(category: str, **kwargs) -> object:
    _sep(f"[1] 상품 생성 — {category}")
    t0 = time.time()

    if category == "planner":
        from generator.planner_html import generate_planner_html
        planner_type = kwargs.get("planner_type", "daily")
        theme_name   = kwargs.get("theme_name", "sage_green")
        niche        = kwargs.get("niche", None)
        product = generate_planner_html(planner_type=planner_type, theme_name=theme_name, niche=niche)

    else:
        logger.error("알 수 없는 카테고리: %s", category)
        return None

    elapsed = time.time() - t0
    if not product:
        logger.error("상품 생성 실패")
        return None

    logger.info("상품 생성 완료: %s (%.1fs)", product.product_id, elapsed)
    logger.info("  카테고리: %s", product.category.value)
    logger.info("  스타일:   %s", product.style)
    logger.info("  키워드:   %s", product.keywords[:5])

    # 파일 검증
    ok_files = 0
    fail_files = 0
    for fp in product.file_paths:
        exists = Path(fp).exists()
        sz = _fmt_size(fp) if exists else "MISSING"
        status = "OK" if exists else "FAIL"
        logger.info("  파일 [%s] %s  (%s)", status, Path(fp).name, sz)
        if exists:
            ok_files += 1
        else:
            fail_files += 1

    _check(ok_files > 0, f"생성 파일 {ok_files}개 OK, {fail_files}개 누락")

    # ZIP 검증 (wall_art / social_media / resume)
    zip_files = [fp for fp in product.file_paths if fp.endswith(".zip")]
    if zip_files:
        import zipfile
        for zp in zip_files:
            try:
                with zipfile.ZipFile(zp) as zf:
                    names = zf.namelist()
                logger.info("  ZIP [%s] — %d개 파일 내부", Path(zp).name, len(names))
                for n in names[:10]:
                    logger.info("    ├ %s", n)
                if len(names) > 10:
                    logger.info("    └ ... 외 %d개", len(names) - 10)
                _check(len(names) >= 3, f"ZIP 내 파일 수 {len(names)}개")
            except Exception as e:
                logger.error("  ZIP 검증 실패: %s", e)

    return product


# ══════════════════════════════════════════════
# 2. 목업 생성
# ══════════════════════════════════════════════

def test_mockups(product) -> list[str]:
    _sep(f"[2] 목업 생성 — {product.product_id}")
    t0 = time.time()

    try:
        from generator.mockup import generate_all_mockups
        mockup_paths = generate_all_mockups(product)
    except Exception as e:
        logger.error("목업 생성 예외: %s", e)
        import traceback
        traceback.print_exc()
        return []

    elapsed = time.time() - t0
    logger.info("목업 생성 완료: %d장 (%.1fs)", len(mockup_paths), elapsed)

    ok = 0
    total_sz = 0
    for mp in mockup_paths:
        exists = Path(mp).exists()
        sz_str = _fmt_size(mp) if exists else "MISSING"
        ext = Path(mp).suffix.upper()
        logger.info("  [%s] %s  %s", "OK" if exists else "FAIL", Path(mp).name, sz_str)
        if exists:
            ok += 1
            try:
                total_sz += Path(mp).stat().st_size
            except Exception:
                pass

    logger.info("목업 결과: %d/%d OK, 총 용량 %.1fMB", ok, len(mockup_paths), total_sz / 1024 / 1024)
    _check(ok >= 8, f"목업 최소 8장 이상: {ok}장")

    # 해상도 검증 (JPG)
    from PIL import Image
    for mp in mockup_paths:
        if mp.endswith(".jpg") and Path(mp).exists():
            try:
                img = Image.open(mp)
                w, h = img.size
                _check(w >= 2000 and h >= 2000,
                       f"{Path(mp).name}: {w}x{h}px (목표 2000px+)")
            except Exception as e:
                logger.warning("  해상도 확인 실패: %s — %s", Path(mp).name, e)
            break  # 첫 JPG만 확인

    return mockup_paths


# ══════════════════════════════════════════════
# 3. SEO 생성 + 채점
# ══════════════════════════════════════════════

def test_seo(product) -> dict:
    _sep(f"[3] SEO 생성 (Groq LLM) — {product.product_id}")
    t0 = time.time()

    try:
        from seo.generator import generate_seo
        result = generate_seo(product)
    except Exception as e:
        logger.error("SEO 생성 예외: %s", e)
        import traceback
        traceback.print_exc()
        return {}

    elapsed = time.time() - t0
    scores = result.get("scores", {})

    logger.info("SEO 생성 완료 (%.1fs)", elapsed)
    logger.info("")
    logger.info("  ── 제목 ──")
    logger.info("  %s", result.get("title", ""))
    logger.info("  길이: %d자 | 점수: %d/10", len(result.get("title", "")), scores.get("title", 0))
    if scores.get("title_issues"):
        for issue in scores["title_issues"]:
            logger.warning("    ! %s", issue)

    logger.info("")
    logger.info("  ── 태그 (%d개) ──", len(result.get("tags", [])))
    for i, tag in enumerate(result.get("tags", []), 1):
        logger.info("    %2d. %s (%d자)", i, tag, len(tag))
    logger.info("  태그 점수: %d/10", scores.get("tags", 0))
    if scores.get("tags_issues"):
        for issue in scores["tags_issues"]:
            logger.warning("    ! %s", issue)

    logger.info("")
    logger.info("  ── 설명 ──")
    desc = result.get("description", "")
    logger.info("  길이: %d자 | 점수: %d/10", len(desc), scores.get("description", 0))
    # 처음 300자만 미리보기
    logger.info("  미리보기: %s...", desc[:300].replace("\n", " / "))
    if scores.get("desc_issues"):
        for issue in scores["desc_issues"]:
            logger.warning("    ! %s", issue)

    logger.info("")
    avg = scores.get("average", 0)
    logger.info("  ── 종합 점수: %.1f/10 ──", avg)
    _check(scores.get("title", 0) >= 8, f"제목 점수 {scores.get('title',0)}/10 >= 8")
    _check(scores.get("tags", 0) >= 8, f"태그 점수 {scores.get('tags',0)}/10 >= 8")
    _check(scores.get("description", 0) >= 8, f"설명 점수 {scores.get('description',0)}/10 >= 8")
    _check(avg >= 8.0, f"평균 점수 {avg}/10 >= 8.0")

    # FAQ/보증 체크
    _check("q:" in desc.lower() or "faq" in desc.lower(),
           "설명에 FAQ 섹션 포함")
    _check("satisfaction" in desc.lower() or "guarantee" in desc.lower() or "make it right" in desc.lower(),
           "설명에 만족 보증 문구 포함")

    return result


# ══════════════════════════════════════════════
# 4. 결과 요약 저장
# ══════════════════════════════════════════════

def save_test_report(category: str, product, mockup_paths: list, seo: dict):
    _sep(f"[4] 테스트 리포트 저장 — {category}")

    report_dir = Path(__file__).parent / "output" / f"test_{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    report_dir.mkdir(parents=True, exist_ok=True)

    # 리포트 텍스트
    lines = [
        f"테스트 날짜: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"카테고리: {category}",
        f"상품 ID: {product.product_id if product else 'N/A'}",
        "",
        "─── 생성 파일 ───",
    ]
    if product:
        for fp in product.file_paths:
            sz = _fmt_size(fp) if Path(fp).exists() else "MISSING"
            lines.append(f"  {Path(fp).name}  ({sz})")

    lines += ["", "─── 목업 ───"]
    for mp in mockup_paths:
        sz = _fmt_size(mp) if Path(mp).exists() else "MISSING"
        lines.append(f"  {Path(mp).name}  ({sz})")

    if seo:
        scores = seo.get("scores", {})
        lines += [
            "",
            "─── SEO 결과 ───",
            f"제목: {seo.get('title', '')}",
            f"제목 점수: {scores.get('title', 0)}/10",
            f"태그 ({len(seo.get('tags', []))}개): {', '.join(seo.get('tags', []))}",
            f"태그 점수: {scores.get('tags', 0)}/10",
            f"설명 길이: {len(seo.get('description', ''))}자",
            f"설명 점수: {scores.get('description', 0)}/10",
            f"평균 점수: {scores.get('average', 0)}/10",
            "",
            "─── 설명 전문 ───",
            seo.get("description", ""),
        ]

    report_path = report_dir / "test_report.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("리포트 저장: %s", report_path)

    # 로그 파일도 복사
    try:
        import shutil
        shutil.copy(str(log_file), str(report_dir / "pipeline.log"))
    except Exception:
        pass

    logger.info("전체 결과 폴더: %s", report_dir)
    return report_dir


# ══════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════

CATEGORIES = ["planner"]


def run_test(category: str, **kwargs):
    logger.info("")
    logger.info("*" * 60)
    logger.info("  FULL DRY-RUN TEST — %s", category.upper())
    if kwargs:
        logger.info("  옵션: %s", kwargs)
    logger.info("  로그: %s", log_file)
    logger.info("*" * 60)

    results = {"pass": 0, "fail": 0}

    # 1. 상품 생성
    product = test_generate(category, **kwargs)
    if not product:
        logger.error("상품 생성 실패 — 테스트 중단")
        results["fail"] += 1
        return results

    results["pass"] += 1

    # 2. 목업
    mockup_paths = test_mockups(product)
    if len(mockup_paths) >= 8:
        results["pass"] += 1
    else:
        results["fail"] += 1

    # 3. SEO
    seo = test_seo(product)
    if seo and seo.get("scores", {}).get("average", 0) >= 7:
        results["pass"] += 1
    else:
        results["fail"] += 1

    # 4. 리포트 저장
    report_dir = save_test_report(category, product, mockup_paths, seo)

    # 최종 요약
    _sep("TEST SUMMARY")
    logger.info("  카테고리:   %s", category)
    logger.info("  PASS:       %d", results["pass"])
    logger.info("  FAIL:       %d", results["fail"])
    logger.info("  결과 폴더:  %s", report_dir)
    logger.info("  로그 파일:  %s", log_file)

    if results["fail"] == 0:
        logger.info("")
        logger.info("  ALL TESTS PASSED — 발행 준비 완료")
    else:
        logger.warning("")
        logger.warning("  %d개 항목 실패 — 위 로그 확인", results["fail"])

    return results


def main():
    parser = argparse.ArgumentParser(description="Etsy 파이프라인 로컬 테스트 (업로드 없음)")
    parser.add_argument("--mock", action="store_true",
                        help="이미지 API 호출 없이 더미 이미지로 전체 파이프라인 테스트 (비용 0)")
    _planner_types  = ["daily", "weekly", "budget", "meal", "habit_tracker",
                       "gratitude", "goal_setting", "fitness"]
    _planner_themes = ["pastel_pink", "sage_green", "ocean_blue", "lavender", "warm_beige",
                       "dark_elegant", "minimal_mono", "terracotta", "forest_green", "coral_peach"]
    _planner_niches = ["ADHD", "anxiety", "christian", "sobriety", "mom",
                       "homeschool", "self_care", "nurse", "teacher", "pregnancy", "entrepreneur",
                       "ADHD_teacher", "ADHD_nurse", "christian_teacher", "sobriety_mom",
                       "perimenopause", "cycle_syncing", "caregiver", "glp1"]
    parser.add_argument("--cat", choices=CATEGORIES + ["all"],
                        default="all", help="테스트할 카테고리 (기본: planner)")
    parser.add_argument("--planner-type",  choices=_planner_types,  default="daily",
                        help="플래너 타입 (기본: daily)")
    parser.add_argument("--planner-theme", choices=_planner_themes, default="sage_green",
                        help="플래너 테마 컬러 (기본: sage_green)")
    parser.add_argument("--planner-niche", choices=_planner_niches, default=None,
                        help="플래너 니치 (기본: generic)")
    args = parser.parse_args()

    if args.mock:
        os.environ["WALL_ART_MOCK"] = "true"
        logger.info("*** MOCK 모드 활성화 — 이미지 API 호출 없음, 비용 $0 ***")

    cats = CATEGORIES if args.cat == "all" else [args.cat]
    total = {"pass": 0, "fail": 0}

    for cat in cats:
        kwargs = {}
        if cat == "planner":
            kwargs = {"planner_type": args.planner_type, "theme_name": args.planner_theme,
                      "niche": args.planner_niche}
        r = run_test(cat, **kwargs)
        total["pass"] += r.get("pass", 0)
        total["fail"] += r.get("fail", 0)

    if len(cats) > 1:
        _sep("TOTAL SUMMARY")
        logger.info("  전체 PASS: %d  FAIL: %d", total["pass"], total["fail"])


if __name__ == "__main__":
    main()
