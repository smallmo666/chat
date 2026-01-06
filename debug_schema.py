import asyncio
from sqlmodel import select
from src.core.database import get_app_db, get_query_db
from src.core.models import Project

async def main():
    try:
        app_db = get_app_db()
        with app_db.get_session() as session:
            statement = select(Project)
            results = session.exec(statement).all()
            
            if not results:
                print("No projects found in AppDatabase.")
                return

            project = results[0]
            print(f"Using Project ID: {project.id}, Name: {project.name}")
            
            query_db = get_query_db(project.id)
            print(f"QueryDB Type: {query_db.type}")
            
            schema = await asyncio.to_thread(query_db.inspect_schema)
            print("Schema Info:")
            print(schema)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
