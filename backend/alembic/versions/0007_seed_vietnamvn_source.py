"""seed nguồn mới vietnam.vn (sitemap chia theo ngày)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-08
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SOURCE_ID = "00000000-0000-0000-0000-000000000007"
PARSING_RULES = json.dumps({"engine": "crawl4ai"})


def upgrade():
    op.execute(
        sa.text(
            """
            INSERT INTO sources
                (source_id, name, domain, group_name, sitemap_url, listing_url, parsing_rules, is_active)
            VALUES
                (:source_id, 'Vietnam.vn', 'vietnam.vn', 'Vietnam.vn',
                 'https://www.vietnam.vn/sitemap.xml', NULL, CAST(:parsing_rules AS jsonb), true)
            ON CONFLICT (domain) DO NOTHING
            """
        ).bindparams(source_id=SOURCE_ID, parsing_rules=PARSING_RULES)
    )


def downgrade():
    op.execute(sa.text("DELETE FROM sources WHERE domain = 'vietnam.vn'"))
