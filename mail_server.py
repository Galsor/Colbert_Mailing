from __future__ import print_function

import base64
import datetime
import pickle
import os.path
import sys
from email.encoders import encode_base64
from pathlib import Path

import httplib2
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid

import mimetypes
import os
from apiclient import errors
from jinja2 import Environment, FileSystemLoader

# The scope defines the level of authorisation requested in the Gmail Account.
# Other scopes available here : # https://docs.python.org/3/library/email-examples.html
# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/gmail.send",
          "https://www.googleapis.com/auth/drive"]


# "https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/spreadsheets".


def get_users():
    gsheet_scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    cred_path = Path() / "credentials_colbert.json"
    creds = ServiceAccountCredentials.from_json_keyfile_name(cred_path, gsheet_scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1Up_W3K2FtRj0yFZEbdmjRj4qx-a6ZTT3QTMDQQedex4").get_worksheet(0)
    mails = sheet.col_values(2)[1:]
    firstnames = sheet.col_values(3)[1:]
    contacts = {n: m for n, m in zip(firstnames, mails)}
    return contacts


class email_html():
    def __init__(self):
        self.template = self.get_html_template()

    @staticmethod
    def get_html_template():
        mail_path = Path() / "mail-template" / 'child.html'
        if mail_path.exists():
            """with codecs.open(mail_path, 'r') as f:
                html = f.read()"""
            templateLoader = FileSystemLoader(searchpath=str(Path() / "mail-template"))
            templateEnv = Environment(loader=templateLoader)
            template = templateEnv.get_template("child.html")
            return template
        else:
            raise FileExistsError(f"Email template (mail.html) not found in mail-template folder.")

    def create_prediction_message(self, sender, user, subject, predictions):
        message = MIMEMultipart(_subtype='related')
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = user[1]

        template = self.get_html_template()
        # TODO : fill template with values using template.render
        bodyContent = self.personalize(template, user, predictions)

        # Create the plain-text and HTML version of your message
        message.attach(MIMEText(bodyContent, "html"))
        message = self.attach_images(message)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {'raw': raw}

    def personalize(self, template, user, predictions):
        today = datetime.date.today()
        if today.weekday() == 4:
            days = 3
        else:
            days = 1
        tomorrow = today + datetime.timedelta(days=days)
        tomorrow_str = tomorrow.strftime("%m/%d/%Y")
        bodyContent = template.render(firstname=user[0], date=tomorrow_str, predictions=predictions)
        return bodyContent

    def attach_images(self, message):
        img_path = Path() / 'mail-template' / 'img'
        p = img_path.glob('**/*')
        files = [x for x in p if x.is_file()]
        for file in files:
            # .png or .jpg
            ext = file.suffix
            # filename without its suffix
            name = file.stem
            with open(file, 'rb') as f:
                img_data = f.read()
            if ext == '.jpg':
                img = MIMEImage(img_data, 'jpeg')
            elif ext == '.png':
                img = MIMEImage(img_data)

            img.add_header('Content-Id', f'<{name}>')  # angle brackets are important
            img.add_header("Content-Disposition", "inline", filename=f"{name}")
            message.attach(img)
        return message


class MailServer():
    def __init__(self):
        self.sender = "me"
        self.creds = self._get_creds()
        self.s = build('gmail', 'v1', credentials=self.creds)

    @staticmethod
    def _get_creds():
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.

        cur_dir = os.path.dirname(os.path.abspath(__file__))
        token_path = os.path.join(cur_dir, 'token.pickle')
        cred_path = os.path.join(cur_dir, 'credentials_mail.json')
        mail_scope = ["https://www.googleapis.com/auth/gmail.send"]
        if not cur_dir in sys.path:
            sys.path.append(cur_dir)

        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    cred_path, mail_scope)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)

        return creds

    def send_message(self, user_id, message):
        """Send an email message.

        Args:
          service: Authorized Gmail API service instance.
          user_id: User's email address. The special value "me"
          can be used to indicate the authenticated user.
          message: Message to be sent.

        Returns:
          Sent Message.
        """
        try:
            req = self.s.users().messages().send(userId=user_id, body=message)
            message = (self.s.users().messages().send(userId=user_id, body=message)
                       .execute())
            print(f"Message Id: {message['id']}")
            return message
        except errors.HttpError as error:
            print(f"An error occurred: {error}")

    def create_message(self, to, subject, message_text):
        """Create a message for an email.

        Args:
          sender: Email address of the sender.
          to: Email address of the receiver.
          subject: The subject of the email message.
          message_text: The text of the email message.

        Returns:
          An object containing a base64url encoded email object.
        """
        message = MIMEText(message_text)
        message['to'] = to
        message['from'] = self.sender
        message['subject'] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {'raw': raw}

    def create_message_with_attachment(self, to, subject, message_text, file_dir,
                                       filename):
        """Create a message for an email.

        Args:
          sender: Email address of the sender.
          to: Email address of the receiver.
          subject: The subject of the email message.
          message_text: The text of the email message.
          file_dir: The directory containing the file to be attached.
          filename: The name of the file to be attached.

        Returns:
          An object containing a base64url encoded email object.
        """
        message = MIMEMultipart()
        message['to'] = to
        message['from'] = self.sender
        message['subject'] = subject

        msg = MIMEText(message_text)
        message.attach(msg)

        path = os.path.join(file_dir, filename)
        content_type, encoding = mimetypes.guess_type(path)

        if content_type is None or encoding is not None:
            content_type = 'application/octet-stream'
        main_type, sub_type = content_type.split('/', 1)
        if main_type == 'text':
            with open(path, 'rb') as fp:
                txt = fp.read().decode()
                msg = MIMEText(txt, _subtype=sub_type)
        elif main_type == 'image':
            # TODO : check if it works
            with open(path, 'rb') as fp:
                msg = MIMEImage(fp.read(), _subtype=sub_type)
        else:
            with open(path, 'rb') as fp:
                msg = MIMEBase(main_type, sub_type)
                msg.set_payload(fp.read())
                encode_base64(msg)

        msg.add_header('Content-Disposition', 'attachment', filename=filename)
        message.attach(msg)

        return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

    def send_predictions(self, predictions):
        users = get_users()
        mail = email_html()
        for user in users.items():
            message = mail.create_prediction_message(self.sender, user, "Colbert predictions", predictions)
            res = self.send_message("me", message)
            print(res)


if __name__ == '__main__':
    predictions = {'aapl': 0, "CA.PA": 1}
    mail = MailServer()

    mess = "This is a test email. Please do not answer it. \n Test UTF-8 : é!°$ù#@ç"
    message = mail.create_message("meilliez.antoine@gmail.com", "Test mail from Colbert n°1", mess)
    # res = mail.send_message("me", message)
    mail.send_predictions(predictions)
