import smtplib, os
pw = os.environ.get('MAIL_PASSWORD') or 'ivmemdnjagglhlgl'
print('Using password length:', len(pw))
s = smtplib.SMTP('smtp.gmail.com', 587, timeout=20)
s.set_debuglevel(1)
s.ehlo()
s.starttls()
s.ehlo()
try:
    s.login('ishwaryaganesan555@gmail.com', pw)
    print('LOGIN OK')
except Exception as e:
    print('LOGIN FAILED:', type(e).__name__, e)
finally:
    s.quit()
