Personal Knowledge Base & Catalog

A lightweight, fast, and fully self-contained web application designed to structure information, maintain a personal inventory of devices and services, and manage a private knowledge base.
Key Features

    FastAPI & SQLite (WAL mode): High performance and stable database operations inside the container, featuring non-blocking read operations during concurrent writes.

    Zero-Configuration Setup: Ready to run out of the box right after cloning the repository — a secure SECRET_KEY for session management is automatically generated in memory if no .env file is present.

    Dynamic Internationalization (i18n): Full UI localization (English by default, Ukrainian, and German) with seamless language switching directly from the login page.

    Role-Based Access Control (RBAC): Flexible user permissions (Admin, Editor, Viewer) with granular read/write controls assigned per individual catalog tab (category).

    Built-in Log Monitoring: An intuitive admin dashboard for real-time application log viewing. Supports dynamic log level changes (DEBUG, INFO, WARNING, ERROR) without container restarts, paired with automatic file rotation (5 MB max) to preserve server disk space.

    One-Click Backup & Restore: Download a full system backup (database + uploaded icons) via the web interface, with fast hot restoration directly from a ZIP archive.

    Docker-Native: Fully optimized for quick deployment using Docker Compose on a home server or mini PC.