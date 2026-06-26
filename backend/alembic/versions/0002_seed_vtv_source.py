"""seed nguồn VTV cho Slice 1 walking skeleton

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-25
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

VTV_SOURCE_ID = "00000000-0000-0000-0000-000000000001"

PARSING_RULES = json.dumps(
    {
        "title": "meta[property='og:title']",
        "content": "div.detail-content",
        "date": "meta[property='article:published_time']",
        "author": "meta[property='article:author']",
    }
)


def upgrade():
    op.execute(
        sa.text(
            """
            INSERT INTO sources (source_id, name, domain, group_name, sitemap_url, parsing_rules, is_active)
            VALUES (:source_id, :name, :domain, :group_name, :sitemap_url, CAST(:parsing_rules AS jsonb), true)
            ON CONFLICT (domain) DO NOTHING
            """
        ).bindparams(
            source_id=VTV_SOURCE_ID,
            name="VTV News",
            domain="vtv.vn",
            group_name="VTV",
            sitemap_url="https://vtv.vn/sitemap.xml",
            parsing_rules=PARSING_RULES,
        )
    )


def downgrade():
    op.execute(sa.text("DELETE FROM sources WHERE domain = 'vtv.vn'"))
