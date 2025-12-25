import os
import random
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv
import json

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

    def regenerate_all_data(self):
        """
        强制重新生成所有数据：
        1. 删除所有现有表（关闭外键检查）
        2. 生成100个业务场景，共1000张表
        """
        print("QueryDB: 正在重置数据库并生成 1000 张表 (100 个业务场景)...")
        inspector = inspect(self.engine)
        existing_tables = inspector.get_table_names()
        
        with self.engine.connect() as conn:
            # 1. Drop all tables
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in existing_tables:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                    print(f"Dropped {table}")
                except Exception as e:
                    print(f"Failed to drop {table}: {e}")
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            conn.commit()

            # 2. 定义 100 个业务场景（领域）
            # 格式: (prefix, domain_name, [list of entity templates])
            domains = []
            
            # 通用实体模板（简化用于批量生成）
            # 我们将使用这些来构建特定领域的表
            entities = [
                ("users", "用户", "id INT PRIMARY KEY, name VARCHAR(50) COMMENT '姓名', email VARCHAR(100) COMMENT '邮箱', role VARCHAR(20) COMMENT '角色', age INT COMMENT '年龄'"),
                ("orders", "订单", "id INT PRIMARY KEY, user_id INT COMMENT '用户ID', amount DECIMAL(10,2) COMMENT '金额', status VARCHAR(20) COMMENT '状态'"),
                ("items", "明细", "id INT PRIMARY KEY, order_id INT COMMENT '订单ID', product_id INT COMMENT '产品ID', qty INT COMMENT '数量'"),
                ("logs", "日志", "id INT PRIMARY KEY, action VARCHAR(50) COMMENT '操作', created_at DATETIME COMMENT '时间'"),
                ("config", "配置", "k VARCHAR(50) PRIMARY KEY COMMENT '键', v VARCHAR(200) COMMENT '值'"),
                ("stats", "统计", "date DATE COMMENT '日期', metric VARCHAR(50) COMMENT '指标', value INT COMMENT '数值'"),
                ("assets", "资产", "id INT PRIMARY KEY, name VARCHAR(100) COMMENT '名称', value DECIMAL(10,2) COMMENT '价值'"),
                ("events", "事件", "id INT PRIMARY KEY, type VARCHAR(50) COMMENT '类型', description TEXT COMMENT '描述'"),
                ("files", "文件", "id INT PRIMARY KEY, filename VARCHAR(100) COMMENT '文件名', size INT COMMENT '大小'"),
                ("tasks", "任务", "id INT PRIMARY KEY, title VARCHAR(100) COMMENT '标题', assignee_id INT COMMENT '执行人', due_date DATE COMMENT '截止日期'")
            ]
            
            # 生成 100 个领域
            categories = [
                ("hr", "人力资源"), ("crm", "客户关系"), ("fin", "财务管理"), ("scm", "供应链"), 
                ("mfg", "制造生产"), ("edu", "教育培训"), ("med", "医疗健康"), ("gov", "政务管理"),
                ("retail", "零售分销"), ("log", "物流配送"), ("it", "信息技术"), ("dev", "研发管理"),
                ("ops", "运维监控"), ("sec", "安全审计"), ("mkt", "市场营销"), ("sup", "客户支持"),
                ("prop", "物业管理"), ("legal", "法务合规"), ("risk", "风险控制"), ("asset", "资产管理")
            ]
            
            count = 0
            for cat_prefix, cat_name in categories:
                for i in range(1, 6): # 每个类别 5 个子域 = 总共 100 个领域
                    domain_code = f"{cat_prefix}{i}"
                    domain_label = f"{cat_name}子域{i}"
                    
                    # 对于每个领域，基于模板创建 10 个表，但带有领域前缀
                    for entity_code, entity_label, columns in entities:
                        table_name = f"{domain_code}_{entity_code}"
                        table_comment = f"{domain_label}-{entity_label}表"
                        
                        # 添加领域特定列以使其多样化
                        extra_col = f"domain_specific_{i} VARCHAR(50) COMMENT '域特定字段'"
                        sql = f"CREATE TABLE {table_name} ({columns}, {extra_col})"
                        
                        try:
                            conn.execute(text(f"{sql} COMMENT='{table_comment}'"))
                            
                            # 插入虚拟数据
                            if "users" in entity_code:
                                conn.execute(text(f"INSERT INTO {table_name} (id, name, email, role, age, domain_specific_{i}) VALUES (1, 'User1', 'u1@test.com', 'admin', 25, 'data')"))
                            elif "orders" in entity_code:
                                conn.execute(text(f"INSERT INTO {table_name} (id, user_id, amount, status, domain_specific_{i}) VALUES (1, 1, 100.00, 'pending', 'data')"))
                                
                        except Exception as e:
                            print(f"Error creating {table_name}: {e}")
                        
                        count += 1
            
            conn.commit()
            print(f"QueryDB: Regeneration complete. Created {count} tables.")

    def ensure_demo_data(self):
        """
        在 querydb 上生成测试表和数据。
        生成具有丰富业务含义的1000张表，覆盖HR、CRM、财务、物流等多个领域。
        """
        inspector = inspect(self.engine)
        existing_tables = inspector.get_table_names()
        
        # 检查我们是否已经有大量的表
        if len(existing_tables) >= 1000:
            print(f"QueryDB: 检测到已有 {len(existing_tables)} 张表，跳过数据生成。")
            return

        print("QueryDB: 正在生成大规模业务领域数据 (1000 张表)...")
        
        with self.engine.connect() as conn:
            
            # 创建表的辅助函数
            def create_table_safe(name, sql, comment):
                if name in existing_tables:
                    return
                try:
                    conn.execute(text(f"{sql} COMMENT='{comment}'"))
                except Exception as e:
                    print(f"Failed to create {name}: {e}")

            # ==========================================
            # 1. 电子商务核心（20 个表）
            # ==========================================
            # 用户、产品、订单通常已经存在，但让我们定义扩展
            
            # 确保核心基础
            if "users" not in existing_tables:
                create_table_safe("users", """
                    CREATE TABLE users (
                        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
                        name VARCHAR(255) COMMENT '用户姓名',
                        email VARCHAR(255) COMMENT '电子邮箱',
                        age INT COMMENT '年龄',
                        joined_year INT COMMENT '注册年份',
                        status VARCHAR(50) COMMENT '状态'
                    )""", "用户信息表")
                # 插入虚拟数据
                try:
                     for i in range(50):
                         conn.execute(text("INSERT INTO users (name, email, age, joined_year, status) VALUES (:name, :email, :age, :year, :status)"), 
                                      {"name": f"User_{i}", "email": f"user{i}@example.com", "age": 20 + (i%40), "year": 2020 + (i%5), "status": "active"})
                except: pass

            if "products" not in existing_tables:
                create_table_safe("products", """
                    CREATE TABLE products (
                        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '商品ID',
                        name VARCHAR(255) COMMENT '商品名称',
                        category VARCHAR(100) COMMENT '商品分类',
                        price DECIMAL(10, 2) COMMENT '价格',
                        stock INT COMMENT '库存数量'
                    )""", "商品信息表")
                try:
                    for i in range(50):
                        conn.execute(text("INSERT INTO products (name, category, price, stock) VALUES (:name, :cat, :price, :stock)"),
                                     {"name": f"Product_{i}", "cat": f"Category_{i%5}", "price": 10.0 + i, "stock": 100})
                except: pass

            if "orders" not in existing_tables:
                create_table_safe("orders", """
                    CREATE TABLE orders (
                        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '订单ID',
                        user_id INT COMMENT '用户ID',
                        total_amount DECIMAL(10, 2) COMMENT '订单总金额',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                        status VARCHAR(50) COMMENT '订单状态',
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )""", "订单表")
                try:
                    user_ids = [row[0] for row in conn.execute(text("SELECT id FROM users")).fetchall()]
                    if user_ids:
                        for i in range(100):
                            conn.execute(text("INSERT INTO orders (user_id, total_amount, status) VALUES (:uid, :amt, :status)"),
                                         {"uid": random.choice(user_ids), "amt": 50.0 + (i%100), "status": "completed"})
                except: pass

            # 扩展电子商务
            create_table_safe("ec_carts", """
                CREATE TABLE ec_carts (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '购物车ID',
                    user_id INT COMMENT '用户ID',
                    updated_at DATETIME COMMENT '更新时间'
                )""", "购物车表")
            
            create_table_safe("ec_cart_items", """
                CREATE TABLE ec_cart_items (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '项ID',
                    cart_id INT COMMENT '购物车ID',
                    product_id INT COMMENT '商品ID',
                    quantity INT COMMENT '数量'
                )""", "购物车明细表")

            create_table_safe("ec_wishlists", """
                CREATE TABLE ec_wishlists (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '收藏夹ID',
                    user_id INT COMMENT '用户ID',
                    product_id INT COMMENT '商品ID',
                    added_at DATETIME COMMENT '添加时间'
                )""", "用户收藏夹")
            
            create_table_safe("ec_reviews", """
                CREATE TABLE ec_reviews (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '评价ID',
                    product_id INT COMMENT '商品ID',
                    user_id INT COMMENT '用户ID',
                    rating INT COMMENT '评分1-5',
                    comment TEXT COMMENT '评价内容',
                    created_at DATETIME COMMENT '评价时间'
                )""", "商品评价表")

            # ==========================================
            # 2. HR 领域（人力资源） - ~150 个表
            # ==========================================
            # 核心 HR
            create_table_safe("hr_employees", """
                CREATE TABLE hr_employees (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '员工ID',
                    first_name VARCHAR(50) COMMENT '名',
                    last_name VARCHAR(50) COMMENT '姓',
                    email VARCHAR(100) COMMENT '邮箱',
                    phone VARCHAR(20) COMMENT '电话',
                    hire_date DATE COMMENT '入职日期',
                    job_id VARCHAR(10) COMMENT '职位ID',
                    salary DECIMAL(8, 2) COMMENT '薪资',
                    department_id INT COMMENT '部门ID'
                )""", "员工信息表")
            
            create_table_safe("hr_departments", """
                CREATE TABLE hr_departments (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '部门ID',
                    name VARCHAR(50) COMMENT '部门名称',
                    location_id INT COMMENT '地点ID'
                )""", "部门表")

            # 不同年份/地区的薪资和考勤
            years = range(2020, 2025)
            regions = ['cn', 'us', 'eu', 'sg', 'jp']
            
            for year in years:
                for month in range(1, 13):
                    create_table_safe(f"hr_payroll_{year}_{month:02d}", """
                        CREATE TABLE hr_payroll_dummy (
                            id INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
                            employee_id INT COMMENT '员工ID',
                            base_salary DECIMAL(10,2) COMMENT '基本工资',
                            bonus DECIMAL(10,2) COMMENT '奖金',
                            tax DECIMAL(10,2) COMMENT '扣税',
                            net_pay DECIMAL(10,2) COMMENT '实发工资'
                        )""".replace('hr_payroll_dummy', f"hr_payroll_{year}_{month:02d}"), 
                        f"{year}年{month}月薪资发放记录")
                    
                    create_table_safe(f"hr_attendance_{year}_{month:02d}", """
                        CREATE TABLE hr_attendance_dummy (
                            id INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
                            employee_id INT COMMENT '员工ID',
                            date DATE COMMENT '日期',
                            check_in TIME COMMENT '上班打卡',
                            check_out TIME COMMENT '下班打卡',
                            status VARCHAR(20) COMMENT '状态'
                        )""".replace('hr_attendance_dummy', f"hr_attendance_{year}_{month:02d}"),
                        f"{year}年{month}月考勤记录")

            # ==========================================
            # 3. CRM 领域（销售和客户） - ~150 个表
            # ==========================================
            create_table_safe("crm_leads", """
                CREATE TABLE crm_leads (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '线索ID',
                    first_name VARCHAR(50) COMMENT '名',
                    last_name VARCHAR(50) COMMENT '姓',
                    company VARCHAR(100) COMMENT '公司',
                    email VARCHAR(100) COMMENT '邮箱',
                    status VARCHAR(20) COMMENT '状态'
                )""", "销售线索表")
            
            create_table_safe("crm_opportunities", """
                CREATE TABLE crm_opportunities (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '商机ID',
                    lead_id INT COMMENT '线索ID',
                    amount DECIMAL(12,2) COMMENT '预计金额',
                    stage VARCHAR(20) COMMENT '阶段',
                    close_date DATE COMMENT '预计成交日期'
                )""", "商机表")

            # 基于区域的客户数据
            for region in regions:
                create_table_safe(f"crm_customers_{region}", """
                    CREATE TABLE crm_customers_dummy (
                        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '客户ID',
                        name VARCHAR(100) COMMENT '客户名称',
                        industry VARCHAR(50) COMMENT '行业',
                        tier VARCHAR(20) COMMENT '等级',
                        account_manager_id INT COMMENT '客户经理ID'
                    )""".replace('crm_customers_dummy', f"crm_customers_{region}"),
                    f"{region.upper()}地区客户表")
                
                # 每个区域的活动
                create_table_safe(f"crm_activities_{region}", """
                    CREATE TABLE crm_activities_dummy (
                        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '活动ID',
                        customer_id INT COMMENT '客户ID',
                        type VARCHAR(20) COMMENT '活动类型',
                        description TEXT COMMENT '描述',
                        date DATETIME COMMENT '时间'
                    )""".replace('crm_activities_dummy', f"crm_activities_{region}"),
                    f"{region.upper()}地区客户活动记录")

            # ==========================================
            # 4. 财务领域（会计） - ~200 个表
            # ==========================================
            create_table_safe("fin_accounts", """
                CREATE TABLE fin_accounts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(50) COMMENT '科目代码',
                    name VARCHAR(255) COMMENT '科目名称'
                )""", "会计科目表")
            
            # 月度日记账和分类账
            for year in years:
                for month in range(1, 13):
                    period = f"{year}_{month:02d}"
                    create_table_safe(f"fin_journal_{year}_{month:02d}", """
                        CREATE TABLE fin_journal_dummy (
                            id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '凭证ID',
                            entry_date DATE COMMENT '凭证日期',
                            description VARCHAR(255) COMMENT '摘要',
                            posted_by INT COMMENT '制单人'
                        )""".replace('fin_journal_dummy', f"fin_journal_{year}_{month:02d}"),
                        f"{year}年{month}月会计凭证")

                    create_table_safe(f"fin_journal_lines_{year}_{month:02d}", """
                        CREATE TABLE fin_journal_lines_dummy (
                            id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '分录ID',
                            journal_id BIGINT COMMENT '凭证ID',
                            account_code VARCHAR(20) COMMENT '科目代码',
                            debit DECIMAL(14,2) COMMENT '借方金额',
                            credit DECIMAL(14,2) COMMENT '贷方金额'
                        )""".replace('fin_journal_lines_dummy', f"fin_journal_lines_{year}_{month:02d}"),
                        f"{year}年{month}月凭证分录")
                    
                    create_table_safe(f"fin_expenses_{year}_{month:02d}", """
                        CREATE TABLE fin_expenses_dummy (
                            id INT AUTO_INCREMENT PRIMARY KEY COMMENT '报销单ID',
                            employee_id INT COMMENT '员工ID',
                            amount DECIMAL(10,2) COMMENT '金额',
                            category VARCHAR(50) COMMENT '类别',
                            status VARCHAR(20) COMMENT '状态'
                        )""".replace('fin_expenses_dummy', f"fin_expenses_{year}_{month:02d}"),
                        f"{year}年{month}月费用报销单")

            # ==========================================
            # 5. 供应链 (SCM) - ~150 个表
            # ==========================================
            create_table_safe("scm_vendors", """
                CREATE TABLE scm_vendors (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255)
                )""", "供应商表")
                
            # 仓库库存
            # 25 个仓库
            for w in range(1, 26):
                create_table_safe(f"scm_inventory_wh_{w}", """
                    CREATE TABLE scm_inventory (
                        product_id INT,
                        quantity INT,
                        location VARCHAR(50)
                    )""", f"仓库 {w} 库存表")

            # ==========================================
            # 6. 项目管理 (PM) - ~100 个表
            # ==========================================
            for i in range(1, 101):
                create_table_safe(f"pm_project_{i}_tasks", """
                    CREATE TABLE pm_tasks (
                        id INT PRIMARY KEY,
                        name VARCHAR(255),
                        status VARCHAR(50)
                    )""", f"项目 {i} 任务表")

            # ==========================================
            # 7. CMS (内容管理) - ~50 个表
            # ==========================================
            cms_modules = ['news', 'blogs', 'videos', 'images', 'comments', 'tags', 'categories', 'users', 'logs', 'settings']
            for mod in cms_modules:
                create_table_safe(f"cms_posts_{site}", """
                    CREATE TABLE cms_posts_dummy (
                        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '文章ID',
                        title VARCHAR(200) COMMENT '标题',
                        content LONGTEXT COMMENT '内容',
                        author_id INT COMMENT '作者ID',
                        published_at DATETIME COMMENT '发布时间'
                    )""".replace('cms_posts_dummy', f"cms_posts_{site}"),
                    f"{site}站点文章表")
                
                create_table_safe(f"cms_comments_{site}", """
                    CREATE TABLE cms_comments_dummy (
                        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '评论ID',
                        post_id INT COMMENT '文章ID',
                        user_name VARCHAR(50) COMMENT '用户',
                        content TEXT COMMENT '评论内容',
                        ip_address VARCHAR(45) COMMENT 'IP'
                    )""".replace('cms_comments_dummy', f"cms_comments_{site}"),
                    f"{site}站点评论表")

            # ==========================================
            # 8. 杂项和日志（剩余以达到 1000）
            # ==========================================
            current_count = len(existing_tables)
            remaining = 1000 - current_count
            
            # 模拟微服务日志
            if remaining > 0:
                print(f"Generating {remaining} log tables to reach 1000...")
                services = ['auth', 'payment', 'search', 'recommend', 'notification', 'user', 'order', 'inventory']
                # 每个服务 20 个日志分片
                for svc in services:
                    for shard in range(1, 21):
                        t_name = f"logs_{svc}_{shard}"
                        create_table_safe(t_name, """
                            CREATE TABLE log_dummy (
                                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                                level VARCHAR(10),
                                message TEXT,
                                created_at DATETIME
                            )""", f"{svc} 服务日志分片 {shard}")
        
        print("QueryDB: 数据生成完成。")

    def inspect_schema(self) -> str:
        """
        批量检查
        """
        inspector = inspect(self.engine)
        schema_info = {}
        
        all_tables = inspector.get_table_names()
        
        for table_name in all_tables:
            # 获取带有注释的列
            columns = inspector.get_columns(table_name)
            # 获取表注释
            try:
                table_comment = inspector.get_table_comment(table_name)
                # 如果可用，Inspect 返回注释
                comment_text = table_comment.get('text', '') if table_comment else ""
            except:
                comment_text = ""
                
            schema_info[table_name] = {
                "columns": [{"name": col["name"], "type": str(col["type"]), "comment": col.get("comment", "")} for col in columns],
                "comment": comment_text
            }
            
        return json.dumps(schema_info, ensure_ascii=False)

    def run_query(self, query: str) -> str:
        """
        在 querydb 上执行 SQL 查询。
        """
        try:
            # 使用显式连接管理，确保事务边界
            with self.engine.connect() as conn:
                try:
                    df = pd.read_sql(query, conn)
                    if df.empty:
                        return "查询执行成功，但结果为空。"
                    return df.to_markdown(index=False)
                except Exception as query_error:
                    # 如果查询出错，显式回滚以重置连接状态，防止污染连接池
                    # "Can't reconnect until invalid transaction is rolled back" 错误通常由此导致
                    conn.rollback()
                    return f"执行查询时出错: {query_error}"
        except Exception as e:
            return f"数据库连接错误: {e}"


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
                        schema_content LONGTEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()
        else:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE db_schema_info MODIFY schema_content LONGTEXT"))
                    conn.commit()
            except Exception as e:
                print(f"Failed to alter schema_content column: {e}")

    def save_schema_info(self, schema_content: str):
        """
        将 querydb 的 schema 信息保存到 testdb。
        """
        with self.engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE db_schema_info"))
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
            return "{}"


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

def get_db():
    return get_query_db()
