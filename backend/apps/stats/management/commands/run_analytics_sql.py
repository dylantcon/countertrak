# apps/stats/management/commands/run_analytics_sql.py
import os
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Run analytics SQL queries from SQL files'

    def add_arguments(self, parser):
        parser.add_argument('query_name', type=str, help='Name of the SQL query file to run (without .sql extension)')
        parser.add_argument('--params', nargs='*', help='Optional parameters for the query in format key=value')

    def handle(self, *args, **options):
        query_name = options['query_name']
        params = {}
        
        if options['params']:
            for param in options['params']:
                key, value = param.split('=')
                params[key] = value
        
        # SQL files directory
        sql_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sql')
        
        sql_file_path = os.path.join(sql_dir, f"{query_name}.sql")
        
        if not os.path.exists(sql_file_path):
            self.stderr.write(self.style.ERROR(f"SQL file not found: {sql_file_path}"))
            return
            
        # Read the SQL file
        with open(sql_file_path, 'r') as f:
            sql_query = f.read()
        
        # Replace parameters in the SQL query
        for key, value in params.items():
            sql_query = sql_query.replace(f"${{{key}}}", value)
        
        # Execute the query
        self.stdout.write(self.style.SUCCESS(f"Executing query from {sql_file_path}"))
        self.stdout.write(self.style.SUCCESS("Query parameters: " + str(params)))
        
        with connection.cursor() as cursor:
            cursor.execute(sql_query)
            
            # Fetch the results if it's a SELECT query
            if sql_query.strip().upper().startswith('SELECT'):
                columns = [col[0] for col in cursor.description]
                results = cursor.fetchall()
                
                # Print results in a tabular format
                self.stdout.write(self.style.SUCCESS(f"Results ({len(results)} rows):"))
                self.stdout.write(self.style.SUCCESS('-' * 80))
                self.stdout.write(self.style.SUCCESS(' | '.join(columns)))
                self.stdout.write(self.style.SUCCESS('-' * 80))
                
                for row in results:
                    self.stdout.write(self.style.SUCCESS(' | '.join(str(cell) for cell in row)))
            else:
                self.stdout.write(self.style.SUCCESS("Query executed successfully."))
