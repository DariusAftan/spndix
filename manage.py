import os
import sys

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    django_project_dir = os.path.join(base_dir, "ProiectDjango")
    if os.path.isdir(django_project_dir) and django_project_dir not in sys.path:
        sys.path.insert(0, django_project_dir)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ProiectDjango.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    main()