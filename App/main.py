"""Application entry point for Untangled Nexus."""
from app.application import Application

def main() -> None:
    application = Application()
    application.run()

if __name__ == "__main__":
    main()
