import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(sender_email, sender_password, recipient_email, subject, body):
    try:
        # Set up the MIME
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = subject

        # Attach the body with the msg instance
        message.attach(MIMEText(body, 'plain'))

        # Create SMTP session for sending the mail
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  # Enable security
            server.login(sender_email, sender_password)  # Login credentials
            server.send_message(message)  # Send the email

        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    # Example usage
    sender_email = "hariharpradeepjaybal@gmail.com"
    sender_password = "dellvostro2006/+++"
    recipient_email = "hariharpradeepjaybal@gmail.com"
    subject = "Meeting Reminder"
    body = "This is a reminder for our meeting scheduled tomorrow at 10 AM."

    send_email(sender_email, sender_password, recipient_email, subject, body)
