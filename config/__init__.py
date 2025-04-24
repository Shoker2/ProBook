from .Configure import Configure

config = Configure(default_config={
    "Database": {
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": "probook",
        "DB_USER": "postgres",
        "DB_PASS": "",
    },
    "Redis": {
        "host": "redis",
        "port": 6379,
        "login": "",
        "password": ""
    },
    "Miscellaneous": {
        "Secret": "",
        "min_available_day_booking": 2,
        "max_available_day_booking": 60,
    },
    "Microsoft": {
        "client_id": "",
        "client_secret": "",
        "tenant_id": "",
        "redirect_url": "http://localhost:8000/auth/microsoft/token"
    }
})
