"""ai answers

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('ai_answers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=True),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('jurisdiction_code', sa.String(length=10), nullable=True),
    sa.Column('language', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('response', sa.JSON(), nullable=False),
    sa.Column('checks', sa.JSON(), nullable=False),
    sa.Column('urgency', sa.JSON(), nullable=False),
    sa.Column('llm_called', sa.Boolean(), nullable=False),
    sa.Column('counts_toward_usage', sa.Boolean(), nullable=False),
    sa.Column('provider', sa.String(length=30), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=False),
    sa.Column('prompt_version', sa.String(length=40), nullable=False),
    sa.Column('provider_request_id', sa.String(length=120), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_answers_case_id'), 'ai_answers', ['case_id'], unique=False)
    op.create_index(op.f('ix_ai_answers_created_at'), 'ai_answers', ['created_at'], unique=False)
    op.create_index(op.f('ix_ai_answers_user_id'), 'ai_answers', ['user_id'], unique=False)
    op.create_table('ai_answer_citations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('answer_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=10), nullable=False),
    sa.Column('cited', sa.Boolean(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=True),
    sa.Column('section_id', sa.UUID(), nullable=True),
    sa.Column('document_sha256', sa.String(length=64), nullable=False),
    sa.Column('source_title', sa.String(length=400), nullable=False),
    sa.Column('section_ref', sa.String(length=60), nullable=False),
    sa.Column('official_url', sa.String(length=1000), nullable=False),
    sa.Column('section_text', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['answer_id'], ['ai_answers.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['section_id'], ['source_sections.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['source_id'], ['legal_sources.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_answer_citations_answer_id'), 'ai_answer_citations', ['answer_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_answer_citations_answer_id'), table_name='ai_answer_citations')
    op.drop_table('ai_answer_citations')
    op.drop_index(op.f('ix_ai_answers_user_id'), table_name='ai_answers')
    op.drop_index(op.f('ix_ai_answers_created_at'), table_name='ai_answers')
    op.drop_index(op.f('ix_ai_answers_case_id'), table_name='ai_answers')
    op.drop_table('ai_answers')
