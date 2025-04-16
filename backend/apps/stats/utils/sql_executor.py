# apps/stats/utils/sql_executor.py
import os
import logging
from django.db import connection
from django.conf import settings
from pathlib import Path

logger = logging.getLogger(__name__)

def get_sql_directory():
    """Return the path to the SQL directory"""
    return Path(__file__).resolve().parent.parent / 'sql'

def execute_sql_file(file_name, params=None):
    """
    Execute a SQL file and return the results
    
    Args:
        file_name: Name of the SQL file (with or without .sql extension)
        params: Dictionary of parameters to replace in the SQL query
    
    Returns:
        List of dictionaries representing the query results
    """
    if not file_name.endswith('.sql'):
        file_name += '.sql'
    
    sql_dir = get_sql_directory()
    sql_file_path = sql_dir / file_name
    
    if not sql_file_path.exists():
        logger.error(f"SQL file not found: {sql_file_path}")
        return None
    
    # Read the SQL file
    with open(sql_file_path, 'r') as f:
        sql_query = f.read()
    
    # Replace parameters in the SQL query
    if params:
        for key, value in params.items():
            # Use PostgreSQL parameter style
            placeholder = f"${{{key}}}"
            if isinstance(value, str):
                # Quote string values
                sql_query = sql_query.replace(placeholder, f"'{value}'")
            else:
                # Non-string values
                sql_query = sql_query.replace(placeholder, str(value))
    
    # Execute the query
    with connection.cursor() as cursor:
        logger.debug(f"Executing SQL: {sql_query}")
        cursor.execute(sql_query)
        
        # If SELECT query, return results
        if sql_query.strip().upper().startswith('SELECT'):
            columns = [col[0] for col in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
        
        # For non-SELECT queries, return affected rows count
        return cursor.rowcount
