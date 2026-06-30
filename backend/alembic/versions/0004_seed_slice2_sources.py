"""seed 5 nguồn mới cho Slice 2 (VOV, VietnamPlus, CAND, BoCongAn, TinGia)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-29
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

CRAWL4AI_RULES = json.dumps({"engine": "crawl4ai"})

TINGIA_LISTING_RULES = json.dumps(
    {
        "engine": "crawl4ai",
        "listing_item": "div.info",
        "listing_link": "h2.title a",
        "listing_date": "span.date",
    }
)

SOURCES = [
    {
        "source_id": "00000000-0000-0000-0000-000000000002",
        "name": "VOV.vn",
        "domain": "vov.vn",
        "group_name": "VOV",
        "sitemap_url": "https://vov.vn/sitemap.xml",
        "listing_url": None,
        "parsing_rules": CRAWL4AI_RULES,
    },
    {
        "source_id": "00000000-0000-0000-0000-000000000003",
        "name": "VietnamPlus",
        "domain": "vietnamplus.vn",
        "group_name": "VietnamPlus",
        "sitemap_url": "https://www.vietnamplus.vn/sitemap.xml",
        "listing_url": None,
        "parsing_rules": CRAWL4AI_RULES,
    },
    {
        "source_id": "00000000-0000-0000-0000-000000000004",
        "name": "Báo Công an Nhân dân",
        "domain": "cand.vn",
        "group_name": "Bộ Công an",
        "sitemap_url": "https://cand.vn/sitemap.xml",
        "listing_url": None,
        "parsing_rules": CRAWL4AI_RULES,
    },
    {
        "source_id": "00000000-0000-0000-0000-000000000005",
        "name": "Cổng TTĐT Bộ Công an",
        "domain": "bocongan.gov.vn",
        "group_name": "Bộ Công an",
        "sitemap_url": "https://bocongan.gov.vn/sitemap.xml",
        "listing_url": None,
        "parsing_rules": CRAWL4AI_RULES,
    },
    {
        "source_id": "00000000-0000-0000-0000-000000000006",
        "name": "Trung tâm Xử lý tin giả",
        "domain": "tingia.gov.vn",
        "group_name": "Trung tâm Xử lý tin giả",
        "sitemap_url": None,
        "listing_url": "https://tingia.gov.vn/",
        "parsing_rules": TINGIA_LISTING_RULES,
    },
]


def upgrade():
    for src in SOURCES:
        op.execute(
            sa.text(
                """
                INSERT INTO sources
                    (source_id, name, domain, group_name, sitemap_url, listing_url, parsing_rules, is_active)
                VALUES
                    (:source_id, :name, :domain, :group_name, :sitemap_url, :listing_url,
                     CAST(:parsing_rules AS jsonb), true)
                ON CONFLICT (domain) DO NOTHING
                """
            ).bindparams(**src)
        )


def downgrade():
    domains = [src["domain"] for src in SOURCES]
    op.execute(sa.text("DELETE FROM sources WHERE domain = ANY(:domains)").bindparams(domains=domains))
