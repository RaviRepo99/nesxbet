from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from email.message import EmailMessage
from html import escape
import os
import smtplib
import json
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
COUNTRY_DATA = ROOT / "web-api" / "country" / "all.html"


def load_dotenv():
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


load_dotenv()

EXTRA_COUNTRIES = [
    {"id": 301, "phoneCode": 43, "name": "Austria", "alpha": "AT"},
    {"id": 302, "phoneCode": 32, "name": "Belgium", "alpha": "BE"},
    {"id": 303, "phoneCode": 357, "name": "Cyprus", "alpha": "CY"},
    {"id": 304, "phoneCode": 353, "name": "Ireland", "alpha": "IE"},
    {"id": 305, "phoneCode": 972, "name": "Israel", "alpha": "IL"},
    {"id": 306, "phoneCode": 352, "name": "Luxembourg", "alpha": "LU"},
    {"id": 307, "phoneCode": 356, "name": "Malta", "alpha": "MT"},
    {"id": 308, "phoneCode": 31, "name": "Netherlands", "alpha": "NL"},
    {"id": 309, "phoneCode": 41, "name": "Switzerland", "alpha": "CH"},
    {"id": 310, "phoneCode": 971, "name": "United Arab Emirates", "alpha": "AE"},
    {"id": 311, "phoneCode": 44, "name": "United Kingdom", "alpha": "GB"},
    {"id": 312, "phoneCode": 1, "name": "United States", "alpha": "US"},
]


class CapturedSiteHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

    def do_GET(self):
        request_path = urlsplit(self.path).path
        if request_path == "/web-api/country/all":
            country_json = COUNTRY_DATA.read_text(encoding="utf-8")
            country_json = country_json.replace("\r", " ").replace("\n", " ")
            countries = json.loads(country_json)
            known = {country["alpha"] for country in countries}
            countries.extend(country for country in EXTRA_COUNTRIES if country["alpha"] not in known)
            payload = json.dumps(countries).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def do_POST(self):
        request_path = urlsplit(self.path).path
        if request_path not in (
            "/api/contact",
            "/web-api/fairpari/contact/send",
            "/web-api/partnership/fxshop",
            "/web-api/partnership/xshop",
        ):
            self.send_error(404, "Not found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 20000:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            is_legacy_contact_form = request_path != "/api/contact"
            fields = {
                "Country": str(payload.get("country", "")).strip(),
                "First name": str(payload.get("name", payload.get("firstName", ""))).strip(),
                "Email": str(payload.get("email", "")).strip(),
                "Phone number": str(payload.get("phone", "")).strip(),
                "Method of contact": str(payload.get("communicationMethod", payload.get("contactMethod", ""))).strip(),
                "Contact details": str(payload.get("communicationContact", payload.get("contactDetails", ""))).strip(),
                "Message": str(payload.get("message", "")).strip(),
            }
            if not fields["First name"] or not fields["Email"] or not fields["Message"]:
                raise ValueError("Please fill in your name, email, and message")
            if "@" not in fields["Email"] or "." not in fields["Email"].rsplit("@", 1)[-1]:
                raise ValueError("Please provide a valid email address")

            smtp_user = os.environ.get("SMTP_USER")
            smtp_password = os.environ.get("SMTP_PASSWORD")
            recipient = os.environ.get("CONTACT_RECIPIENT", "nesxbet@gmail.com")
            if not smtp_user or not smtp_password:
                raise RuntimeError("Email is not configured. Set SMTP_USER and SMTP_PASSWORD.")

            body = "\n".join("{}: {}".format(label, value or "-") for label, value in fields.items())
            detail_rows = "".join(
                "<tr><td style=\"padding:12px 0;color:#9fb9ad;font-size:13px;width:38%;\">{}</td>"
                "<td style=\"padding:12px 0;color:#ffffff;font-size:14px;font-weight:600;\">{}</td></tr>".format(
                    escape(label), escape(value or "-")
                )
                for label, value in fields.items()
                if label != "Message"
            )
            html_body = """\
<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#031b14;font-family:Arial,Helvetica,sans-serif;color:#ffffff;">
    <div style="max-width:620px;margin:0 auto;background:#062e24;border:1px solid #1f6b49;border-radius:16px;overflow:hidden;">
      <div style="padding:28px 30px;background:linear-gradient(135deg,#0b5b3d,#062e24);">
        <div style="font-size:13px;letter-spacing:2px;color:#84cc16;font-weight:700;">NESXBET</div>
        <h1 style="margin:10px 0 5px;font-size:25px;color:#ffffff;">New agent enquiry</h1>
        <p style="margin:0;color:#c5e2d3;font-size:14px;">A new partnership request was submitted from your website.</p>
      </div>
      <div style="padding:24px 30px;">
        <table style="width:100%;border-collapse:collapse;">{}</table>
        <div style="margin-top:18px;padding:18px;background:#0a3b2d;border-left:4px solid #22c55e;border-radius:8px;">
          <div style="margin-bottom:8px;color:#9fb9ad;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Message</div>
          <div style="color:#ffffff;font-size:15px;line-height:1.6;white-space:pre-wrap;">{}</div>
        </div>
        <a href="mailto:{}" style="display:inline-block;margin-top:24px;padding:13px 20px;border-radius:8px;background:#22c55e;color:#032217;text-decoration:none;font-size:14px;font-weight:700;">Reply to applicant</a>
      </div>
      <div style="padding:16px 30px;background:#041f18;color:#799b8b;font-size:12px;">This message was sent from the NesXbet agent contact form.</div>
    </div>
  </body>
</html>
""".format(detail_rows, escape(fields["Message"]), escape(fields["Email"], quote=True))
            message = EmailMessage()
            message["Subject"] = "New NesXbet agent enquiry from {}".format(fields["First name"])
            message["From"] = smtp_user
            message["To"] = recipient
            message["Reply-To"] = fields["Email"]
            message.set_content(body)
            message.add_alternative(html_body, subtype="html")

            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
                smtp.login(smtp_user, smtp_password)
                smtp.send_message(message)
            response = {"ok": True, "message": "Message sent successfully"}
            if is_legacy_contact_form:
                response["message_key"] = "contact_message_sent"
            self.send_json(200, response)
        except ValueError as error:
            self.send_json(400, {"ok": False, "message": str(error)})
        except Exception as error:
            print("Contact email failed:", error)
            self.send_json(500, {"ok": False, "message": "Unable to send message right now"})

    def send_json(self, status, data):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def guess_type(self, path):
        request_path = urlsplit(self.path).path
        if request_path.startswith("/web-api/") or request_path.startswith("/translate-api/"):
            return "application/json"
        return super().guess_type(path)

    def translate_path(self, path):
        request_path = urlsplit(path).path
        candidate = ROOT / request_path.lstrip("/")

        if not candidate.exists() and candidate.suffix == "":
            captured_response = candidate.with_suffix(".html")
            if captured_response.is_file():
                return str(captured_response)
            return str(ROOT / "index.html")

        return str(candidate)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 3000), CapturedSiteHandler).serve_forever()
