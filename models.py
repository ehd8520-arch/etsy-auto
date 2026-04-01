"""
Etsy Digital Shop - Data Models
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Category(str, Enum):
    PLANNER               = "planner"
    WORKSHEET             = "worksheet"
    SPREADSHEET           = "spreadsheet"
    WALL_ART              = "wall_art"
    SOCIAL_MEDIA_TEMPLATE = "social_media_template"
    RESUME_TEMPLATE       = "resume_template"


class ProductStatus(str, Enum):
    CREATED = "created"
    MOCKUP_DONE = "mockup_done"
    SEO_DONE = "seo_done"
    UPLOADED = "uploaded"
    PUBLISHED = "published"
    FAILED = "failed"


class Platform(str, Enum):
    ETSY = "etsy"


@dataclass
class Product:
    """Generated digital product."""
    product_id: str
    category: Category
    style: str                          # "{planner_type}_{theme_name}_{niche}"
    keywords: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    mockup_paths: list[str] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    status: ProductStatus = ProductStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    video_path: str = ""          # MP4 listing video path (empty if not generated)


@dataclass
class SEOData:
    """SEO metadata for a listing."""
    title: str
    tags: list[str] = field(default_factory=list)
    description: str = ""
    price_usd: float = 0.0


@dataclass
class Listing:
    """A published listing on Etsy."""
    listing_id: str
    product_id: str
    platform: Platform
    seo: Optional[SEOData] = None
    price_usd: float = 0.0
    views: int = 0
    favorites: int = 0
    sales: int = 0
    reviews: int = 0
    rating: float = 0.0
    published_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)
