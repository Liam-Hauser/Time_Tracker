from alembic import context

def run_migrations_online() -> None:
    from database.db import engine
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            render_as_batch=True,  # required for SQLite ALTER TABLE support
        )
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
