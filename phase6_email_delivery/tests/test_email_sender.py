import os
import unittest
from unittest.mock import patch, MagicMock
from phase6_email_delivery.services.email_sender import EmailSender

class TestEmailSender(unittest.TestCase):
    def setUp(self):
        self.input_md = "test_weekly_pulse.md"
        self.output_md = "test_email_draft.md"
        self.output_txt = "test_email_draft.txt"
        
        with open(self.input_md, "w", encoding="utf-8") as f:
            f.write("# Weekly Pulse\nThis is a test pulse content.")
            
    def tearDown(self):
        for f in [self.input_md, self.output_md, self.output_txt]:
            if os.path.exists(f):
                os.remove(f)
                
    @patch('smtplib.SMTP')
    def test_dry_run_mode(self, mock_smtp):
        sender = EmailSender(self.input_md, self.output_md, self.output_txt)
        sender.process(send_mode=False, recipient="test@example.com")
        
        self.assertTrue(os.path.exists(self.output_md))
        self.assertTrue(os.path.exists(self.output_txt))
        
        with open(self.output_txt, "r", encoding="utf-8") as f:
            content = f.read()
            
        self.assertIn("Subject: [Weekly Pulse] Groww Mutual Fund Reviews", content)
        self.assertIn("Hi Team,", content)
        self.assertIn("This is a test pulse content.", content)
        self.assertIn("Regards", content)
        
        mock_smtp.assert_not_called()

    @patch('smtplib.SMTP')
    @patch.dict(os.environ, {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "testuser",
        "SMTP_PASSWORD": "testpassword",
        "EMAIL_TO": "test@example.com"
    })
    def test_send_mode(self, mock_smtp):
        # Create a mock server instance
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        sender = EmailSender(self.input_md, self.output_md, self.output_txt)
        
        # Test default env email
        sender.process(send_mode=True, recipient=None)
        
        # Check smtp calls
        mock_smtp.assert_called_with("smtp.gmail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("testuser", "testpassword")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

if __name__ == "__main__":
    unittest.main()
