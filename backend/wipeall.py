import os
import sys
import subprocess
import pexpect
from dotenv import load_dotenv

# THIS MUST BE RUN FROM `backend/` !!!! IT WILL NOT WORK OTHERWISE
"""
-========================================================-
Here's the template for .env, just for your own reference.
-========================================================-
# Django settings
DEBUG=True
SECRET_KEY=replace_this_with_a_secret_key
ALLOWED_HOSTS=localhost,127.0.0.1
BASE_DIR=/path/to/countertrak/backend/manage.py   # apparently this is what base_dir means

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=countertrak
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# GSI server
GSI_HOST=0.0.0.0
GSI_PORT=3000
GSI_DEFAULT_AUTH_TOKEN=S8RL9Z6Y22TYQK45JB4V8PHRJJMD9DS9

# Steam API
STEAM_API_KEY=your_steam_api_key

# Logging
LOG_LEVEL=DEBUG

-========================================================-
This file, wipeall.py, is intended to automate the following:
-========================================================-
# access PostgreSQL
sudo -u postgres psql countertrak

# in PostgreSQL shell:
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;


# then run migrations again
python manage.py migrate
python manage.py load_weapons
"""

# load environment variables from .env file in the backend directory
load_dotenv()

def main():

    POSTGRES_PASSWORD = os.getenv('DB_PASSWORD')
    POSTGRES_USER = os.getenv('DB_USER')
    DATABASE_NAME = os.getenv('DB_NAME')

    if not POSTGRES_PASSWORD:
        print("[wipeall.py]: Unable to extract PSQL password from .env")
        return

    if not POSTGRES_USER:
        print("[wipeall.py]: Unable to extract PSQL user from .env")
        return

    if not DATABASE_NAME:
        print("[wipeall.py]: Unable to extract countertrak database name from .env")
        return

    # flush db manually using django management commands
    pychild = pexpect.spawn("python manage.py flush", encoding='utf-8')
    pychild.logfile = sys.stdout
    pychild.expect("Type 'yes' to continue, or 'no' to cancel:")
    pychild.sendline("yes")

    # sign into PSQL shell with supplied credentials
    child = pexpect.spawn(f"sudo -u {POSTGRES_USER} psql {DATABASE_NAME}", encoding='utf-8')

    # pipe to standard output
    child.logfile = sys.stdout
    child.expect(f"Password for user {POSTGRES_USER}:")
    child.sendline(POSTGRES_PASSWORD)

    # okay, now watch for active shell. once found, start executing commands
    child.expect(f"{DATABASE_NAME}=#")
    child.sendline("DROP SCHEMA public CASCADE;")
    child.sendline("CREATE SCHEMA public;")
    child.sendline(f"GRANT ALL ON SCHEMA public TO {POSTGRES_USER};")
    child.sendline("GRANT ALL ON SCHEMA public TO public;")
    child.sendline(r"\q")
    
    os.system("python manage.py migrate")
    os.system("python manage.py load_weapons")

    print("[wipeall.py]: Your counterTrak database has been reset.")

if __name__ == "__main__":
    main()
