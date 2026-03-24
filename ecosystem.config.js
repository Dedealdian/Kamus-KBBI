module.exports = {
  apps : [{
    name: "kbbi-bot",
    script: "kamus.py", // tadi Anda menamainya kamus.py
    interpreter: "venv/bin/python3", // Memastikan PM2 pakai venv
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    error_file: "logs/err.log",
    out_file: "logs/out.log",
    log_date_format: "YYYY-MM-DD HH:mm:ss"
  }]
};
