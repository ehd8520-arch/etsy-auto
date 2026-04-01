# -*- coding: utf-8 -*-
"""
preview_generator.py — 생성된 상품 전체를 Etsy 레이아웃 HTML 미리보기로 출력.

사용:
    from preview_generator import generate_preview
    generate_preview(items, output_path="preview_latest.html", open_browser=True)
"""
import base64
import logging
import webbrowser
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 최대 썸네일 인코딩 크기 (너무 크면 HTML 비대해짐) ──
_MAX_IMG_KB = 400


def _img_b64(path: str) -> str:
    """이미지 파일 → base64 data URI. 실패 시 빈 문자열."""
    try:
        p = Path(path)
        if not p.exists():
            return ""
        data = p.read_bytes()
        if len(data) > _MAX_IMG_KB * 1024:
            # 크기 초과 시 Pillow로 리사이즈 후 인코딩
            try:
                from PIL import Image
                import io
                img = Image.open(p).convert("RGB")
                img.thumbnail((600, 600))
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=75)
                data = buf.getvalue()
            except Exception:
                pass
        ext = p.suffix.lower().lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png"}.get(ext, "jpeg")
        return f"data:image/{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return ""


def _escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _card_html(idx: int, product, seo) -> str:
    """상품 1개 카드 HTML 생성."""
    title       = _escape(getattr(seo, "title", "") or "")
    price       = getattr(seo, "price_usd", 0.0)
    tags        = getattr(seo, "tags", []) or []
    description = _escape(getattr(seo, "description", "") or "")
    style       = _escape(getattr(product, "style", "") or "")
    category    = _escape(getattr(product, "category", "").value if hasattr(getattr(product, "category", ""), "value") else str(getattr(product, "category", "")))

    # 목업 이미지 (최대 10장, MP4 제외)
    mockup_paths = [p for p in (getattr(product, "mockup_paths", []) or [])
                    if not p.endswith(".mp4")][:10]
    imgs = []
    for mp in mockup_paths:
        b64 = _img_b64(mp)
        if b64:
            imgs.append((Path(mp).name, b64))

    # 영상 배지 제거 (Etsy 디지털 리스팅 video 미지원)
    has_video = False

    # 이미지 갤러리 HTML
    if imgs:
        main_img = f'<img id="main-{idx}" src="{imgs[0][1]}" class="main-img" alt="mockup">'
        thumbs = ""
        for ti, (name, b64) in enumerate(imgs):
            active = "active" if ti == 0 else ""
            thumbs += (
                f'<img src="{b64}" class="thumb {active}" '
                f'onclick="switchImg({idx},{ti})" alt="{_escape(name)}">'
            )
        gallery_html = f"""
        <div class="gallery">
          <div class="main-wrap">{main_img}</div>
          <div class="thumbs" id="thumbs-{idx}">{thumbs}</div>
        </div>"""
    else:
        gallery_html = '<div class="gallery no-img">이미지 없음</div>'

    # 태그 pills
    tags_html = "".join(f'<span class="tag">{_escape(t)}</span>' for t in tags)

    # 설명 (첫 줄 훅 굵게, 나머지 pre-line으로 렌더)
    desc_lines = description.split("\n") if description else []
    if desc_lines and desc_lines[0].strip():
        rest = "\n".join(desc_lines[1:]).strip()
        desc_html = f'<p class="hook">{desc_lines[0]}</p>'
        if rest:
            desc_html += f'<p class="desc-body">{rest}</p>'
    else:
        desc_html = f'<p class="desc-body">{description}</p>'

    video_badge = '<span class="badge video-badge">🎬 영상 있음</span>' if has_video else ""

    return f"""
<div class="card" id="card-{idx}">
  <div class="card-left">{gallery_html}</div>
  <div class="card-right">
    <div class="meta">{category} · {style} {video_badge}</div>
    <h2 class="title">{title}</h2>
    <div class="price">${price:.2f}</div>

    <div class="section-label">태그 ({len(tags)}개)</div>
    <div class="tags">{tags_html}</div>

    <div class="section-label">설명</div>
    <div class="desc">{desc_html}</div>
  </div>
</div>
"""


def generate_preview(items: list, output_path: str = "preview_latest.html",
                     open_browser: bool = True) -> str:
    """
    items: list of {{"product": Product, "seo": SEOData, "combo": dict}}
    HTML 미리보기 파일 생성 후 경로 반환.
    open_browser=True 면 기본 브라우저로 자동 오픈.
    """
    if not items:
        logger.warning("preview_generator: 상품 없음")
        return ""

    cards = ""
    nav_links = ""
    valid_count = 0
    for i, item in enumerate(items, 1):
        product = item.get("product")
        seo     = item.get("seo")
        if not product or not seo:
            continue
        valid_count += 1
        combo  = item.get("combo", {})
        label  = f"{combo.get('planner_type','?')} × {combo.get('theme_name','?')}"
        niche  = combo.get("niche") or "generic"
        cards    += _card_html(valid_count, product, seo)
        nav_links += f'<a href="#card-{valid_count}">{valid_count}. {_escape(label)} [{_escape(niche)}]</a>\n'

    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
    count    = valid_count

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Etsy Preview — {now_str} ({count}개)</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f7f7f7; color: #222; line-height: 1.6; }}

  /* ── 상단 네비 ── */
  .topbar {{ background: #f1641e; color: #fff; padding: 12px 24px;
             display: flex; align-items: center; gap: 16px; flex-wrap: wrap; position: sticky; top: 0; z-index: 100; }}
  .topbar h1 {{ font-size: 16px; font-weight: 700; white-space: nowrap; }}
  .topbar .nav {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .topbar .nav a {{ color: #fff; text-decoration: none; font-size: 12px;
                    background: rgba(0,0,0,.2); padding: 3px 8px; border-radius: 12px; white-space: nowrap; }}
  .topbar .nav a:hover {{ background: rgba(0,0,0,.4); }}

  /* ── 카드 ── */
  .card {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1);
           margin: 24px auto; max-width: 1100px; display: flex; gap: 0;
           scroll-margin-top: 60px; overflow: hidden; }}

  /* ── 갤러리 ── */
  .card-left {{ width: 420px; min-width: 420px; background: #fafafa; padding: 16px; }}
  .gallery {{ display: flex; flex-direction: column; gap: 8px; }}
  .main-wrap {{ width: 100%; aspect-ratio: 1; overflow: hidden; border-radius: 6px; background: #eee; }}
  .main-img {{ width: 100%; height: 100%; object-fit: cover; display: block; cursor: zoom-in; }}
  .thumbs {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .thumb {{ width: 58px; height: 58px; object-fit: cover; border-radius: 4px;
            cursor: pointer; border: 2px solid transparent; transition: border-color .15s; }}
  .thumb.active {{ border-color: #f1641e; }}
  .thumb:hover {{ border-color: #ccc; }}
  .no-img {{ display: flex; align-items: center; justify-content: center;
             height: 200px; color: #aaa; font-size: 14px; }}

  /* ── 정보 패널 ── */
  .card-right {{ flex: 1; padding: 24px; overflow-y: auto; max-height: 80vh; }}
  .meta {{ font-size: 12px; color: #888; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }}
  .badge {{ font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }}
  .video-badge {{ background: #e8f4ff; color: #1a6ec9; }}
  .title {{ font-size: 20px; font-weight: 700; line-height: 1.4; margin-bottom: 10px; color: #111; }}
  .price {{ font-size: 22px; color: #f1641e; font-weight: 700; margin-bottom: 18px; }}
  .section-label {{ font-size: 11px; font-weight: 700; color: #888; text-transform: uppercase;
                    letter-spacing: .8px; margin: 16px 0 8px; }}
  .tags {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .tag {{ background: #f5f5f5; border: 1px solid #e0e0e0; padding: 3px 10px;
          border-radius: 14px; font-size: 12px; color: #444; }}
  .desc {{ font-size: 13px; color: #333; }}
  .hook {{ font-weight: 600; font-size: 14px; margin-bottom: 10px; color: #111; }}
  .desc-body {{ white-space: pre-line; }}

  /* ── 줌 오버레이 ── */
  #zoom-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,.85);
                   z-index: 999; align-items: center; justify-content: center; cursor: zoom-out; }}
  #zoom-overlay.show {{ display: flex; }}
  #zoom-img {{ max-width: 90vw; max-height: 90vh; border-radius: 6px; }}

  @media (max-width: 700px) {{
    .card {{ flex-direction: column; }}
    .card-left {{ width: 100%; min-width: 0; }}
    .card-right {{ max-height: none; }}
  }}
</style>
</head>
<body>

<div class="topbar">
  <h1>🛍 Etsy Preview — {now_str} ({count}개)</h1>
  <div class="nav">{nav_links}</div>
</div>

{cards}

<div id="zoom-overlay" onclick="closeZoom()">
  <img id="zoom-img" src="" alt="zoom">
</div>

<script>
function switchImg(cardIdx, thumbIdx) {{
  const mainImg = document.getElementById('main-' + cardIdx);
  const thumbContainer = document.getElementById('thumbs-' + cardIdx);
  const thumbs = thumbContainer.querySelectorAll('.thumb');
  mainImg.src = thumbs[thumbIdx].src;
  thumbs.forEach(t => t.classList.remove('active'));
  thumbs[thumbIdx].classList.add('active');
}}

document.querySelectorAll('.main-img').forEach(img => {{
  img.addEventListener('click', () => {{
    document.getElementById('zoom-img').src = img.src;
    document.getElementById('zoom-overlay').classList.add('show');
  }});
}});

function closeZoom() {{
  document.getElementById('zoom-overlay').classList.remove('show');
}}

document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') closeZoom();
}});
</script>
</body>
</html>"""

    try:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        logger.info("미리보기 생성 완료: %s (%d개 상품)", out.name, count)
        logger.info("미리보기 경로: %s", out.resolve())
        if open_browser:
            _open_file(out.resolve())
        return str(out)
    except Exception as e:
        logger.error("미리보기 생성 실패: %s", e)
        return ""


def _open_file(path: Path) -> None:
    """OS별 파일 열기 (Windows: os.startfile, 기타: webbrowser)."""
    import sys as _sys
    try:
        if _sys.platform == "win32":
            import os as _os
            _os.startfile(str(path))
        else:
            webbrowser.open(path.as_uri())
    except Exception as e:
        logger.warning("브라우저 자동 오픈 실패: %s — 수동으로 열어주세요: %s", e, path)
