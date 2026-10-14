"""Alembic-versioned initial application schema."""
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, String, JSON, Integer

def upgrade(engine):
    with engine.begin() as conn:
        context=MigrationContext.configure(conn)
        current=context.get_current_revision()
        if current=="0001":return
        if current is not None:raise RuntimeError("Unknown database revision; do not overwrite")
        op=Operations(context)
        op.create_table("records",Column("id",String,primary_key=True),Column("kind",String,nullable=False),Column("data",JSON,nullable=False))
        op.create_index("ix_records_kind","records",["kind"])
        op.create_table("events",Column("seq",Integer,primary_key=True,autoincrement=True),Column("call_id",String,nullable=False),Column("data",JSON,nullable=False))
        op.create_index("ix_events_call_id","events",["call_id"])
        context._ensure_version_table()
        conn.exec_driver_sql("INSERT INTO alembic_version(version_num) VALUES ('0001')")
