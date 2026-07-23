import getpass
from app import create_app
from app.db import seed_admin, validate_password_strength
from app.config import Config

app = create_app()


@app.cli.command("create-admin")
def create_admin():
    """Create the initial admin user interactively."""
    import sys

    username = input("Admin username: ").strip()
    if not username:
        print("Username cannot be empty.")
        sys.exit(1)
    password = getpass.getpass("Admin password: ")
    if not password:
        print("Password cannot be empty.")
        sys.exit(1)
    ok, msg = validate_password_strength(password)
    if not ok:
        print(f"Password does not meet requirements: {msg}")
        sys.exit(1)
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)
    result = seed_admin(username, password)
    if result is True:
        print(f"Admin user '{username}' created.")
    else:
        error = result[1] if isinstance(result, tuple) else "Unknown error"
        print(f"Admin creation failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
