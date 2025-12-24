# Regenerate 1000 Tables with 100 Business Scenarios

This plan addresses the request to drop all existing tables and regenerate 1000 tables covering 100 diverse business scenarios (domains), suitable for multi-table join testing.

## 1. Domain Design (100 Scenarios)
We will define 100 distinct business domains. Each domain will have ~10 related tables, totaling 1000 tables.

**Sample Categories & Prefixes:**
1.  **HR & Admin**: `hr_recruitment`, `hr_payroll`, `hr_training`, `admin_assets`, `admin_booking`...
2.  **Commerce & Retail**: `retail_pos`, `retail_inventory`, `ecommerce_orders`, `marketing_campaigns`, `crm_support`...
3.  **Finance**: `fin_ledger`, `fin_budget`, `fin_tax`, `fin_audit`, `fin_billing`...
4.  **Supply Chain**: `scm_procurement`, `scm_logistics`, `scm_warehouse`, `mfg_production`, `mfg_quality`...
5.  **Services**: `svc_hotel`, `svc_hospital`, `svc_education`, `svc_transport`, `svc_event`...
6.  **IT & Tech**: `it_assets`, `it_tickets`, `dev_projects`, `ops_monitoring`, `sec_audit`...
7.  **Industry Specific**: `energy_grid`, `telecom_billing`, `real_estate_sales`, `auto_dealer`, `insurance_claims`...

**Schema Standards:**
-   **Naming**: `domain_entity_suffix` (e.g., `hr_payroll_salary_slips`).
-   **Comments**: Full Chinese comments for tables and columns.
-   **Types**: Use `INT`, `DECIMAL`, `VARCHAR`, `DATETIME`, `TEXT` appropriately.
-   **Relations**: Include `user_id`, `dept_id`, `product_id` etc. to allow joins, even without explicit Foreign Key constraints (as requested).

## 2. Implementation Logic (`src/utils/db.py`)

### `regenerate_all_data(self)` Method
-   **Drop All**: Iterate and drop all existing tables in `querydb`.
-   **Generators**:
    -   Create a list of 100 `DomainGenerator` objects/functions.
    -   Each generator is responsible for creating ~10 tables for its specific domain.
    -   Use loops and templates to ensure diversity and avoid simple suffixing.
-   **Execution**:
    -   Disable FK checks (`SET FOREIGN_KEY_CHECKS=0`).
    -   Drop tables.
    -   Run generators.
    -   Enable FK checks.

## 3. Trigger Mechanism (`src/server.py`)
-   Add a **POST /admin/regenerate** endpoint.
-   This endpoint calls `query_db.regenerate_all_data()`.
-   It then triggers a schema refresh (`inspect_schema` -> `save_schema_info`).

## 4. Frontend Update (Optional but Recommended)
-   The frontend will automatically reflect the changes after the next refresh because the schema browser fetches from the API.

## 5. Execution Steps
1.  **Modify `src/utils/db.py`**: Add `regenerate_all_data` with the 100-domain logic.
2.  **Modify `src/server.py`**: Add the API endpoint.
3.  **Trigger**: Use `curl` or a script to trigger the regeneration.

