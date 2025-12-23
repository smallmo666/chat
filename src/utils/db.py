import os
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

load_dotenv()

class QueryDatabase:
    """
    查询数据库类 (querydb)，负责实际的数据查询和测试数据生成。
    """
    def __init__(self):
        self.host = os.getenv("QUERY_DB_HOST")
        self.port = os.getenv("QUERY_DB_PORT", "3306")
        self.user = os.getenv("QUERY_DB_USER")
        self.password = os.getenv("QUERY_DB_PASSWORD")
        self.dbname = os.getenv("QUERY_DB_NAME")
        
        self.connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
        
        try:
            self.engine = create_engine(self.connection_string)
            print(f"成功连接到 Query Database: {self.host}:{self.port}/{self.dbname}")
        except Exception as e:
            print(f"Query Database 连接失败: {e}")
            raise e

    def ensure_demo_data(self):
        """
        在 querydb 上生成测试表和数据。
        """
        inspector = inspect(self.engine)
        if "users" not in inspector.get_table_names():
            print("QueryDB: 检测到 'users' 表不存在，正在创建并填充演示数据...")
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255),
                        age INT,
                        joined_year INT
                    )
                """))
                
                users = [
                    {"name": "Alice", "age": 30, "joined_year": 2021},
                    {"name": "Bob", "age": 25, "joined_year": 2022},
                    {"name": "Charlie", "age": 35, "joined_year": 2023},
                    {"name": "David", "age": 28, "joined_year": 2023},
                    {"name": "Eve", "age": 22, "joined_year": 2024}
                ]
                
                for user in users:
                    conn.execute(text("INSERT INTO users (name, age, joined_year) VALUES (:name, :age, :joined_year)"), user)
                
                conn.commit()
            print("QueryDB: 'users' 表创建完成。")

    def inspect_schema(self) -> str:
        """
        从 querydb 获取实时的 Schema 信息。
        """
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()
        
        schema_info = []
        for table in table_names:
            columns = inspector.get_columns(table)
            col_strings = [f"{col['name']} ({col['type']})" for col in columns]
            schema_info.append(f"表名: {table}\n列: {', '.join(col_strings)}")
            
        return "\n\n".join(schema_info)

    def run_query(self, query: str) -> str:
        """
        在 querydb 上执行 SQL 查询。
        """
        try:
            df = pd.read_sql(query, self.engine)
            if df.empty:
                return "查询执行成功，但结果为空。"
            return df.to_markdown(index=False)
        except Exception as e:
            return f"执行查询时出错: {e}"


class AppDatabase:
    """
    应用数据库类 (testdb)，负责应用数据持久化和存储 querydb 的库表信息。
    """
    def __init__(self):
        self.host = os.getenv("APP_DB_HOST")
        self.port = os.getenv("APP_DB_PORT", "3306")
        self.user = os.getenv("APP_DB_USER")
        self.password = os.getenv("APP_DB_PASSWORD")
        self.dbname = os.getenv("APP_DB_NAME")
        
        self.connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
        
        try:
            self.engine = create_engine(self.connection_string)
            print(f"成功连接到 App Database: {self.host}:{self.port}/{self.dbname}")
            self.init_metadata_table()
        except Exception as e:
            print(f"App Database 连接失败: {e}")
            raise e

    def init_metadata_table(self):
        """
        初始化用于存储 Schema 信息的表。
        """
        inspector = inspect(self.engine)
        if "db_schema_info" not in inspector.get_table_names():
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE db_schema_info (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        schema_content TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()

    def save_schema_info(self, schema_content: str):
        """
        将 querydb 的 schema 信息保存到 testdb。
        这里简化为只保留最新的一条记录。
        """
        with self.engine.connect() as conn:
            # 清空旧数据
            conn.execute(text("TRUNCATE TABLE db_schema_info"))
            # 插入新数据
            conn.execute(text("INSERT INTO db_schema_info (schema_content) VALUES (:content)"), {"content": schema_content})
            conn.commit()
        print("Schema 信息已同步到 App Database。")

    def get_stored_schema_info(self) -> str:
        """
        从 testdb 获取存储的 schema 信息。
        """
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT schema_content FROM db_schema_info ORDER BY id DESC LIMIT 1")).fetchone()
            if result:
                return result[0]
            return "暂无 Schema 信息，请先同步。"


# 全局实例
query_db_instance = None
app_db_instance = None

def get_query_db():
    global query_db_instance
    if query_db_instance is None:
        query_db_instance = QueryDatabase()
    return query_db_instance

def get_app_db():
    global app_db_instance
    if app_db_instance is None:
        app_db_instance = AppDatabase()
    return app_db_instance

# 为了兼容旧代码（如果有遗漏），保留 get_db 指向 query_db，但建议尽快迁移
def get_db():
    return get_query_db()
