from typing import List, Dict, Union

def format_schema_str(schema_data: Union[Dict, List, str]) -> str:
    """
    Standardize schema information into a string format.
    Handles both dictionary (full schema) and list (search results) inputs.
    """
    if isinstance(schema_data, str):
        return schema_data

    formatted_tables = []
    
    # Handle dict: {"table_name": {"columns": [...]}}
    if isinstance(schema_data, dict):
        for table, info in schema_data.items():
            columns = info if isinstance(info, list) else info.get("columns", [])
            col_strings = []
            for col in columns:
                comment = f" - {col.get('comment')}" if col.get('comment') else ""
                col_strings.append(f"{col['name']} ({col['type']}){comment}")
            
            table_comment = info.get("comment", "") if isinstance(info, dict) else ""
            header = f"Table: {table}"
            if table_comment:
                header += f" ({table_comment})"
            
            formatted_tables.append(f"{header}\nColumns: {', '.join(col_strings)}")

    # Handle list of matches (search results)
    elif isinstance(schema_data, list):
        # Assuming list of dicts with 'table', 'columns' etc. or simple list of table names?
        # This depends on searcher output. Let's assume standard format if possible.
        pass

    return "\n\n".join(formatted_tables)
