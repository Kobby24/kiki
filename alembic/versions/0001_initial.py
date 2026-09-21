"""initial Sikapa schema"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("phone_number", sa.String(30)),
        sa.Column("preferred_language", sa.String(10), nullable=False),
        sa.Column("accessibility_preferences", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    status = sa.Enum(
        "DRAFT",
        "AWAITING_CONFIRMATION",
        "CONFIRMED",
        "AWAITING_AUTHORIZATION",
        "AUTHORIZED",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "SIMULATED",
        name="cashoutstatus",
    )
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "cashout_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("input_method", sa.String(20), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("intent_confidence", sa.Numeric(4, 3)),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("authorization_status", sa.String(30), nullable=False),
        sa.Column("transaction_reference", sa.String(100)),
        sa.Column("agent_message", sa.Text()),
        sa.Column("simulation", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_cashout_requests_user_id", "cashout_requests", ["user_id"])
    op.create_table(
        "communications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "cashout_request_id",
            sa.Uuid(),
            sa.ForeignKey("cashout_requests.id"),
            nullable=False,
        ),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("message_type", sa.String(40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("audio_reference", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_communications_cashout_request_id", "communications", ["cashout_request_id"]
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column(
            "cashout_request_id", sa.Uuid(), sa.ForeignKey("cashout_requests.id")
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_index("ix_communications_cashout_request_id", table_name="communications")
    op.drop_table("communications")
    op.drop_index("ix_cashout_requests_user_id", table_name="cashout_requests")
    op.drop_table("cashout_requests")
    sa.Enum(name="cashoutstatus").drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
