from neo4j_utils import merge_person
from getpass import getpass
from neo4j_utils import log_audit

def create_user_cli():
    try:
        name = input("Enter user name: ")
        role = input("Role (User/Admin) [User]: ") or "User"
        merge_person(name, role)
        log_audit("USER_CREATED", {"name": name, "role": role})
        print(f"✓ {name} ({role}) created/updated.")
    except Exception as e:
        print(f"Error creating user: {e}")

def login_cli() -> str:
    try:
        name = input("Name: ")
        print(f"Welcome, {name}")
        log_audit("USER_LOGIN", {"name": name})
        return name
    except Exception as e:
        print(f"Error during login: {e}")
        return ""
