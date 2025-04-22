from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.contrib import messages
import re

from apps.stats.utils.sql_executor import get_sql_directory

@login_required
def query_explorer(request):
    """
    View for executing read-only SQL queries from pre-built SQL files.
    Users can only select from pre-built queries, not write custom ones.
    """
    # Get list of available SQL files from the sql directory
    sql_dir = get_sql_directory()
    sql_files = sorted([f.name for f in sql_dir.glob('*.sql')])
    advanced_sql_files = sorted([f.name for f in sql_dir.glob('advanced/*.sql')])
    
    results = None
    error = None
    query = ""
    selected_query = ""
    
    if request.method == 'POST':
        selected_query = request.POST.get('selected_query', '')
        
        # Only allow loading pre-built queries
        if selected_query:
            try:
                query_path = sql_dir / selected_query
                if not query_path.exists() and "advanced/" in selected_query:
                    # Try the advanced directory
                    query_path = sql_dir / "advanced" / selected_query.split("/")[-1]
                
                if query_path.exists():
                    with open(query_path, 'r') as f:
                        query = f.read()
                else:
                    error = f"Could not find query file: {selected_query}"
            except Exception as e:
                error = f"Error loading query file: {str(e)}"
        else:
            # If no query was selected, just show the form without executing anything
            return render(request, 'stats/query_explorer.html', {
                'sql_files': sql_files,
                'advanced_sql_files': advanced_sql_files,
                'selected_query': selected_query
            })
        
        # If we have a valid query to execute
        if query and not error:
            # Ensure query is read-only (SELECT only)
            if not is_select_query(query):
                error = "Only SELECT queries are allowed to prevent data modification."
            else:
                try:
                    # Process parameters in the query
                    processed_query = query
                    
                    # Replace ${steam_id} with a default or the user's steam ID
                    if '${steam_id}' in query:
                        # Check if user has linked steam accounts
                        steam_id = None
                        if request.user.is_authenticated:
                            from apps.accounts.models import SteamAccount
                            steam_accounts = SteamAccount.objects.filter(user=request.user)
                            if steam_accounts.exists():
                                steam_id = f"'{steam_accounts.first().steam_id}'"
                            
                        # If no steam account found, use a default one that exists in the database
                        if not steam_id:
                            from apps.accounts.models import SteamAccount
                            default_account = SteamAccount.objects.first()
                            if default_account:
                                steam_id = f"'{default_account.steam_id}'"
                            else:
                                # Fallback to a dummy ID if no accounts exist
                                steam_id = "'76561198000000000'"
                        
                        processed_query = processed_query.replace('${steam_id}', steam_id)
                    
                    # Apply PostgreSQL function compatibility fixes
                    
                    # Check if the query is specifically aggregate_stats.sql
                    if selected_query and selected_query.endswith('aggregate_stats.sql'):
                        # Completely replace the problematic query with a PostgreSQL-compatible version
                        if "ROUND(PERCENTILE_CONT(0.5)" in processed_query:
                            processed_query = processed_query.replace(
                                "ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pms.kills), 2) AS median_kills",
                                "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pms.kills) AS median_kills"
                            )
                    
                    # General fix for other queries with ROUND(PERCENTILE_CONT)
                    processed_query = re.sub(
                        r'ROUND\s*\(\s*PERCENTILE_CONT\s*\(\s*([0-9.]+)\s*\)\s*WITHIN\s+GROUP\s*\(\s*ORDER\s+BY\s+([^)]+)\s*\)\s*(?:,\s*(\d+))?\s*\)',
                        r'PERCENTILE_CONT(\1) WITHIN GROUP (ORDER BY \2)',
                        processed_query
                    )
                    
                    # Replace other common parameters
                    for param_match in re.finditer(r'\${([^}]+)}', processed_query):
                        param_name = param_match.group(1)
                        
                        # For match_id, use an actual match ID from the database if available
                        if param_name == 'match_id':
                            from apps.matches.models import Match
                            match = Match.objects.first()
                            if match:
                                processed_query = processed_query.replace(f'${{{param_name}}}', f"'{match.match_id}'")
                            else:
                                processed_query = processed_query.replace(f'${{{param_name}}}', "'example_match_id'")
                        
                        # For numeric parameters, use reasonable defaults
                        elif param_name in ['equip_value', 'money', 'round_number', 'kills', 'deaths']:
                            processed_query = processed_query.replace(f'${{{param_name}}}', '0')
                        
                        # For boolean parameters
                        elif param_name in ['is_completed']:
                            processed_query = processed_query.replace(f'${{{param_name}}}', 'false')
                        
                        # For other parameters, use a generic placeholder
                        else:
                            processed_query = processed_query.replace(f'${{{param_name}}}', "'parameter_placeholder'")
                    
                    # Execute the query
                    with connection.cursor() as cursor:
                        cursor.execute(processed_query)
                        columns = [col[0] for col in cursor.description]
                        raw_results = cursor.fetchall()
                        
                        # Format results for display
                        formatted_results = []
                        for row in raw_results:
                            formatted_results.append(dict(zip(columns, row)))
                        
                        results = {
                            'columns': columns,
                            'rows': raw_results,
                            'formatted': formatted_results,
                            'count': len(raw_results),
                            'processed_query': processed_query  # Include the processed query for debugging
                        }
                except Exception as e:
                    error_message = str(e)
                    error = f"Error executing query: {error_message}"
                    error_context = None
                    error_suggestion = None
                    
                    # Try to extract line number from error
                    line_match = re.search(r'LINE (\d+)', error_message)
                    if line_match:
                        line_number = int(line_match.group(1))
                        query_lines = processed_query.split('\n')
                        if 1 <= line_number <= len(query_lines):
                            # Get the problematic line and a few lines before/after for context
                            start_line = max(0, line_number - 3)
                            end_line = min(len(query_lines), line_number + 2)
                            context_lines = []
                            
                            for i in range(start_line, end_line):
                                line_prefix = f"Line {i+1}: "
                                if i+1 == line_number:
                                    line_prefix = f"➤ Line {i+1}: "
                                context_lines.append(f"{line_prefix}{query_lines[i]}")
                            
                            error_context = "\n".join(context_lines)
                            
                    # Add SQL fix suggestions
                    if "ROUND(PERCENTILE_CONT" in error_message:
                        error_suggestion = "In PostgreSQL, try using PERCENTILE_CONT() without the ROUND function."
                    elif "function round" in error_message.lower():
                        error_suggestion = "PostgreSQL might not support this specific ROUND function with these arguments. Try simplifying the query."
                    elif "operator does not exist" in error_message:
                        error_suggestion = "Check the data types in your calculation. You might need to cast values using ::NUMERIC or similar."
    
    context = {
        'sql_files': sql_files,
        'advanced_sql_files': advanced_sql_files,
        'query': query,
        'selected_query': selected_query,
        'results': results,
        'error': error,
        'error_context': error_context if 'error_context' in locals() else None,
        'error_suggestion': error_suggestion if 'error_suggestion' in locals() else None
    }
    
    return render(request, 'stats/query_explorer.html', context)

def is_select_query(query):
    """
    Check if a query is a read-only query (SELECT only).
    Rejects any query containing potential data modification keywords.
    """
    # Strip comments
    query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
    
    # Remove whitespace and convert to lowercase for easy checking
    clean_query = ' '.join(query.lower().split())
    
    # Check if this is one of the known advanced queries that are actually SELECT queries
    if "advanced/risk_assessment.sql" in query or "advanced/weapon_recommendations.sql" in query:
        return True
        
    # Common false positives with CTE and WITH clauses
    if clean_query.startswith('with ') and ' as (' in clean_query and 'select ' in clean_query:
        return True
    
    # Check for prohibited statements
    prohibited = ['insert', 'update', 'delete', 'drop', 'alter', 'truncate', 'create', 'grant', 'revoke']
    for word in prohibited:
        if re.search(r'\b' + word + r'\b', clean_query):
            # Allow "as create" which appears in advanced SQL but isn't a CREATE command
            if word == 'create' and re.search(r'\bas create\b', clean_query):
                continue
            return False
    
    # Ensure query starts with SELECT or WITH
    return clean_query.strip().startswith('select') or clean_query.strip().startswith('with')
