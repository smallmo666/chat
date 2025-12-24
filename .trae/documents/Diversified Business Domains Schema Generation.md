# Diversified Business Domains Schema Generation

This plan addresses the requirement to replace repetitive, suffix-based table names (e.g., `logs_2020_01`) with a rich variety of distinct business domains (HR, CRM, Finance, Logistics, etc.) to simulate a real-world enterprise database.

## 1. Domain Design & Schema Definitions

We will introduce 8-10 distinct business domains, each with multiple related tables. Total target: ~1000 tables.

### Domain 1: HR & Organization (人力资源)
-   **Tables**: `employees`, `departments`, `jobs`, `job_history`, `salaries`, `attendance`, `leaves`, `performance_reviews`, `candidates`, `interviews`.
-   **Prefix**: `hr_`

### Domain 2: CRM & Sales (客户关系)
-   **Tables**: `leads`, `opportunities`, `contacts`, `accounts`, `campaigns`, `activities`, `contracts`, `support_tickets`, `feedback`.
-   **Prefix**: `crm_`

### Domain 3: Supply Chain & Logistics (供应链)
-   **Tables**: `suppliers`, `purchase_orders`, `po_items`, `shipments`, `routes`, `vehicles`, `drivers`, `warehouses`, `inventory_transactions`.
-   **Prefix**: `scm_`

### Domain 4: Finance & Accounting (财务)
-   **Tables**: `gl_accounts`, `journal_entries`, `invoices`, `payments`, `expenses`, `budgets`, `assets`, `tax_records`, `audit_logs`.
-   **Prefix**: `fin_`

### Domain 5: Project Management (项目管理)
-   **Tables**: `projects`, `tasks`, `milestones`, `sprints`, `issues`, `comments`, `attachments`, `time_entries`.
-   **Prefix**: `pm_`

### Domain 6: Content Management (内容管理)
-   **Tables**: `articles`, `categories`, `tags`, `authors`, `comments`, `media`, `pages`, `menus`.
-   **Prefix**: `cms_`

### Domain 7: E-learning (在线教育)
-   **Tables**: `courses`, `modules`, `lessons`, `quizzes`, `enrollments`, `certificates`, `instructors`.
-   **Prefix**: `edu_`

### Domain 8: Healthcare (医疗 - Optional/Simulated)
-   **Tables**: `patients`, `doctors`, `appointments`, `prescriptions`, `medical_records`, `billing`.
-   **Prefix**: `hlth_`

### Strategy for 1000 Tables
Since manually defining 1000 distinct schemas is impractical, we will:
1.  **Core Tables**: Define ~50-100 high-quality core tables across the above domains with specific schemas.
2.  **Sharded/Partitioned Tables**: For high-volume data (like logs, transactions), use meaningful partitioning (e.g., `fin_journal_2023`, `scm_shipments_region_us`).
3.  **Module Variations**: Generate tables for different subsidiaries or branches (e.g., `hr_us_employees`, `hr_cn_employees`).
4.  **Microservices Simulation**: Simulate a microservices architecture where similar tables exist in different service namespaces (e.g., `svc_order_orders`, `svc_payment_transactions`).

## 2. Implementation Plan (`src/utils/db.py`)

### Refactor `ensure_demo_data`
-   Remove the loop that generates `extra_data_i`.
-   Implement a `generate_domain_schema(domain_name, table_templates)` function.
-   **Data Structure**: Create a large dictionary mapping domains to their table definitions (SQL + Comment).

### Schema Generation Logic
-   **HR**: Generate core HR tables.
-   **CRM**: Generate core CRM tables.
-   **Finance**: Generate monthly/yearly financial tables (meaningful suffix).
-   **Logistics**: Generate warehouse-specific inventory tables.
-   **SaaS Tenants**: Simulate a multi-tenant system where `tenant_A_users`, `tenant_B_users` exist (a common real-world pattern contributing to high table counts).

## 3. Execution Steps
1.  **Define Schema Templates**: Create a helper class/dict in `db.py` containing the SQL definitions for the new domains.
2.  **Update Generation Loop**: Replace the old loops with domain-based generation.
3.  **Verify**: Ensure the total count reaches ~1000 and names are semantically rich.

## 4. Frontend & API
-   No changes needed for API or Frontend as they already support dynamic schema fetching and tree view. The new table names will automatically appear in the tree.

