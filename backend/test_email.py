from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'ishwaryaganesan555@gmail.com'
app.config['MAIL_PASSWORD'] = 'kyuxefupzofaeiha'  # New app password (no spaces)
app.config['MAIL_DEFAULT_SENDER'] = 'ishwaryaganesan555@gmail.com'

mail = Mail(app)

# Test sending an email
with app.app_context():
    try:
        msg = Message(
            subject="Test Email from Flask",
            recipients=["ishwaryaganesan555@gmail.com"],  # Send to yourself
            body="Hello! This is a test email from Flask-Mail."
        )
        mail.send(msg)
        print("✅ Email sent successfully!")
    except Exception as e:
        print("⚠ Email error:", e)
