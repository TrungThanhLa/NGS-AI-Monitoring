"""tingia.gov.vn: chuyển từ listing-page sang sitemap curated (sitemap_pages)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-08
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

OLD_PARSING_RULES = json.dumps(
    {
        "engine": "crawl4ai",
        "listing_item": "div.info",
        "listing_link": "h2.title a",
        "listing_date": "span.date",
    }
)
OLD_LISTING_URL = "https://tingia.gov.vn/"

NEW_PARSING_RULES = json.dumps(
    {
        "engine": "crawl4ai",
        "sitemap_pages": [
            "https://tingia.gov.vn/sitemap/tin-vua-check.xml",
            "https://tingia.gov.vn/sitemap/multimedia.xml",
            "https://tingia.gov.vn/sitemap/cong-bo-tin-gia.xml",
            "https://tingia.gov.vn/sitemap/vaccine-phong-chong-tin-gia.xml",
            "https://tingia.gov.vn/sitemap/linh-vuc.xml",
        ],
    }
)


def upgrade():
    op.execute(
        sa.text(
            """
            UPDATE sources
            SET parsing_rules = CAST(:parsing_rules AS jsonb), sitemap_url = NULL, listing_url = NULL
            WHERE domain = 'tingia.gov.vn'
            """
        ).bindparams(parsing_rules=NEW_PARSING_RULES)
    )


def downgrade():
    op.execute(
        sa.text(
            """
            UPDATE sources
            SET parsing_rules = CAST(:parsing_rules AS jsonb), sitemap_url = NULL, listing_url = :listing_url
            WHERE domain = 'tingia.gov.vn'
            """
        ).bindparams(parsing_rules=OLD_PARSING_RULES, listing_url=OLD_LISTING_URL)
    )
