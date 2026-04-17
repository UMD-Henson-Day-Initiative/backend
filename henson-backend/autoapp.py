
"""Create an application instance."""
from app import create_app

# Module-level app instance for gunicorn WSGI
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

