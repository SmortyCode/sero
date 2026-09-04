"""Wachen fuer die Landing sero.ltd -- SEO, Brand, Draft-first."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAND = (ROOT / "landing/index.html").read_text(encoding="utf-8")
ROBOTS = (ROOT / "landing/robots.txt").read_text(encoding="utf-8")
SITEMAP = (ROOT / "landing/sitemap.xml").read_text(encoding="utf-8")


def test_robots_und_sitemap_echte_dateien():
    assert ROBOTS.lstrip().startswith("User-agent:")
    assert "Sitemap: https://sero.ltd/sitemap.xml" in ROBOTS
    assert SITEMAP.lstrip().startswith("<?xml")
    assert "<loc>https://sero.ltd/</loc>" in SITEMAP
    assert "<html" not in ROBOTS.lower()
    assert "<html" not in SITEMAP.lower()


def test_title_meta_canonical_draft_story():
    assert "<title>SERO \u2014 Photo to eBay draft for collectibles</title>" in LAND
    assert 'rel="canonical" href="https://sero.ltd/"' in LAND
    assert "Nothing goes live until you say so" in LAND
    assert "PHOTO IN. EBAY OUT." in LAND
    assert "https://app.sero.ltd/app/" in LAND
    assert "--ink: #1C1C1E" in LAND
    assert "background: #000;" not in LAND
    assert "color: #000;" not in LAND
    assert "color: #000000;" not in LAND


def test_keine_falschen_socials_keine_alten_dateien():
    assert "instagram.com" not in LAND.lower()
    assert "tiktok.com" not in LAND.lower()
    assert "https://x.com/seroltd" in LAND
    assert "FAQPage" in LAND
    assert not (ROOT / "landing/landing.css").exists()
    assert not (ROOT / "landing/landing.js").exists()
    assert not (ROOT / "landing/en/index.html").exists()
    assert (ROOT / "landing/assets/reel/01-photo.jpg").exists()
    assert (ROOT / "landing/assets/stills/slab.jpg").exists()
