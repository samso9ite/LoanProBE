# Environment Variables Setup

This project uses environment variables for configuration to enhance security and flexibility. Follow these steps to set up your environment:

## 1. Copy the Example Environment File

```bash
cp .env.example .env
```

## 2. Configure Your Environment Variables

Edit the `.env` file with your actual values:

### Required Variables

- `SECRET_KEY`: Django secret key (generate a new one for production)
- `DEBUG`: Set to `False` in production
- `DATABASE_PASSWORD`: Your database password (if using PostgreSQL)
- `EMAIL_HOST_USER`: Your email address for sending emails
- `EMAIL_HOST_PASSWORD`: Your email app password
- `TWILIO_ACCOUNT_SID`: Your Twilio account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio auth token
- `TWILIO_FROM_NUMBER`: Your Twilio phone number

### Optional Variables (with defaults)

- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `DATABASE_ENGINE`: Database engine (defaults to SQLite)
- `DATABASE_NAME`: Database name
- `REDIS_URL`: Redis connection URL
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed CORS origins
- `TIME_ZONE`: Application timezone
- `LOG_LEVEL`: Logging level

## 3. Database Configuration

### For Development (SQLite - Default)
No additional configuration needed. The app will use SQLite by default.

### For Production (PostgreSQL)
Set these variables in your `.env` file:
```
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=your_db_name
DATABASE_USER=your_db_user
DATABASE_PASSWORD=your_db_password
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

## 4. Security Best Practices

- Never commit the `.env` file to version control
- Use strong, unique passwords and secret keys
- Set `DEBUG=False` in production
- Use HTTPS in production (`SESSION_COOKIE_SECURE=True`)
- Regularly rotate sensitive credentials

## 5. Generating a Secret Key

You can generate a new Django secret key using:

```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

## 6. Email Configuration

For Gmail, you'll need to:
1. Enable 2-factor authentication
2. Generate an app password
3. Use the app password in `EMAIL_HOST_PASSWORD`

## 7. Twilio Configuration

1. Sign up for a Twilio account
2. Get your Account SID and Auth Token from the dashboard
3. Purchase a phone number for sending SMS

## Environment File Location

The `.env` file should be placed in the project root directory (same level as `manage.py`).