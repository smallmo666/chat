import sys
import os
from sqlalchemy import text, inspect

# Add project root to path
sys.path.append(os.getcwd())

from src.core.database import get_app_db

def migrate_db():
    print("Starting database schema migration...")
    db = get_app_db()
    engine = db.engine
    
    with engine.connect() as conn:
        # Check and alter data_sources table
        columns_ds = inspect(engine).get_columns("data_sources")
        col_names_ds = [c["name"] for c in columns_ds]
        
        if "organization_id" not in col_names_ds:
            print("Adding organization_id column to data_sources table...")
            try:
                conn.execute(text("ALTER TABLE data_sources ADD COLUMN organization_id INT"))
                conn.commit()
                print("Success.")
            except Exception as e:
                print(f"Failed to alter data_sources: {e}")
        else:
            print("data_sources table already has organization_id column.")

        # Check for owner_id in data_sources
        if "owner_id" not in col_names_ds:
            print("Adding owner_id column to data_sources table...")
            try:
                conn.execute(text("ALTER TABLE data_sources ADD COLUMN owner_id INT"))
                conn.commit()
                print("Success.")
            except Exception as e:
                print(f"Failed to alter data_sources: {e}")

        # Check and alter projects table
        columns_proj = inspect(engine).get_columns("projects")
        col_names_proj = [c["name"] for c in columns_proj]
        
        if "organization_id" not in col_names_proj:
            print("Adding organization_id column to projects table...")
            try:
                conn.execute(text("ALTER TABLE projects ADD COLUMN organization_id INT"))
                conn.commit()
                print("Success.")
            except Exception as e:
                print(f"Failed to alter projects: {e}")
        else:
            print("projects table already has organization_id column.")
            
        # Check for owner_id in projects
        if "owner_id" not in col_names_proj:
            print("Adding owner_id column to projects table...")
            try:
                conn.execute(text("ALTER TABLE projects ADD COLUMN owner_id INT"))
                conn.commit()
                print("Success.")
            except Exception as e:
                print(f"Failed to alter projects: {e}")

        # Check for node_model_config in projects
        if "node_model_config" not in col_names_proj:
            print("Adding node_model_config column to projects table...")
            try:
                # Assuming JSON type for node_model_config, using JSON for MySQL/PostgreSQL
                # MySQL uses JSON, PostgreSQL uses JSON or JSONB
                # Since we are using SQLAlchemy with SQLModel's sa_type=JSON, we should use JSON type in DB
                conn.execute(text("ALTER TABLE projects ADD COLUMN node_model_config JSON"))
                conn.commit()
                print("Success.")
            except Exception as e:
                print(f"Failed to alter projects for node_model_config: {e}")

        # Check and alter llm_providers table
        # Note: Table might not exist yet if it's new, but create_all handles creation.
        # We only care if it exists but misses columns.
        inspector = inspect(engine)
        if inspector.has_table("llm_providers"):
            columns_llm = inspector.get_columns("llm_providers")
            col_names_llm = [c["name"] for c in columns_llm]
            
            if "organization_id" not in col_names_llm:
                print("Adding organization_id column to llm_providers table...")
                try:
                    conn.execute(text("ALTER TABLE llm_providers ADD COLUMN organization_id INT"))
                    conn.commit()
                    print("Success.")
                except Exception as e:
                    print(f"Failed to alter llm_providers: {e}")
            else:
                print("llm_providers table already has organization_id column.")
        else:
             print("llm_providers table does not exist yet (will be created by app startup).")

        # Check and alter audit_logs table
        if inspector.has_table("audit_logs"):
            columns_audit = inspector.get_columns("audit_logs")
            col_names_audit = [c["name"] for c in columns_audit]
            
            if "user_id" not in col_names_audit:
                print("Adding user_id column to audit_logs table...")
                try:
                    conn.execute(text("ALTER TABLE audit_logs ADD COLUMN user_id INT"))
                    conn.commit()
                    print("Success.")
                except Exception as e:
                    print(f"Failed to alter audit_logs: {e}")
            else:
                print("audit_logs table already has user_id column.")

            # Check for generated_dsl
            if "generated_dsl" not in col_names_audit:
                print("Adding generated_dsl column to audit_logs table...")
                try:
                    conn.execute(text("ALTER TABLE audit_logs ADD COLUMN generated_dsl TEXT"))
                    conn.commit()
                    print("Success.")
                except Exception as e:
                    print(f"Failed to alter audit_logs for generated_dsl: {e}")

            # Check for total_tokens
            if "total_tokens" not in col_names_audit:
                print("Adding total_tokens column to audit_logs table...")
                try:
                    conn.execute(text("ALTER TABLE audit_logs ADD COLUMN total_tokens INT DEFAULT 0"))
                    conn.commit()
                    print("Success.")
                except Exception as e:
                    print(f"Failed to alter audit_logs for total_tokens: {e}")

            # Check for estimated_cost
            if "estimated_cost" not in col_names_audit:
                print("Adding estimated_cost column to audit_logs table...")
                try:
                    conn.execute(text("ALTER TABLE audit_logs ADD COLUMN estimated_cost FLOAT DEFAULT 0.0"))
                    conn.commit()
                    print("Success.")
                except Exception as e:
                    print(f"Failed to alter audit_logs for estimated_cost: {e}")

            # Check for feedback_rating
            if "feedback_rating" not in col_names_audit:
                print("Adding feedback_rating column to audit_logs table...")
                try:
                    conn.execute(text("ALTER TABLE audit_logs ADD COLUMN feedback_rating INT"))
                    conn.commit()
                    print("Success.")
                except Exception as e:
                    print(f"Failed to alter audit_logs for feedback_rating: {e}")

            # Check for feedback_comment
            if "feedback_comment" not in col_names_audit:
                print("Adding feedback_comment column to audit_logs table...")
                try:
                    conn.execute(text("ALTER TABLE audit_logs ADD COLUMN feedback_comment TEXT"))
                    conn.commit()
                    print("Success.")
                except Exception as e:
                    print(f"Failed to alter audit_logs for feedback_comment: {e}")
        else:
             print("audit_logs table does not exist yet.")

    print("Migration check complete.")

if __name__ == "__main__":
    migrate_db()
