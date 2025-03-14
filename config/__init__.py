from .Configure import Configure

config = Configure(default_config={
    "Database": {
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": "probook",
        "DB_USER": "postgres",
        "DB_PASS": "",
    },
    "SMTP": {
        "server": "smtp.mail.ru",
        "port": 587,
        "email": "",
        "password": ""
    },
    "Redis": {
        "host": "redis",
        "port": 6379
    },
    "Miscellaneous": {
        "Secret": "",
    },
    "Microsoft": {
        "client_id": "",
        "client_secret": "",
        "redirect_url": "http://localhost:8000/auth/microsoft/token"
    }
})
