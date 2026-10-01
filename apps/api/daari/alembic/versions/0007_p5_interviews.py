"""P5 candidate questions and anonymous interview sessions."""
from alembic import op

revision = "0007_p5_interviews"
down_revision = "0006_p3_search_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE interview_questions (
        id text PRIMARY KEY, company text NOT NULL, role text NOT NULL,
        payload jsonb NOT NULL, embedding vector(256) NOT NULL, content_hash text NOT NULL
    )""")
    op.execute("CREATE INDEX interview_company_role ON interview_questions(company, role)")
    op.execute("""CREATE TABLE interview_sessions (
        id uuid PRIMARY KEY, payload jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL
    )""")


def downgrade() -> None:
    op.execute("DROP TABLE interview_sessions")
    op.execute("DROP TABLE interview_questions")
