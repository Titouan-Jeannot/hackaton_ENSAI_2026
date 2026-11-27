"""Envoi des emails transactionnels (confirmation d'adresse).

Deux transports :
- SMTP, dès que BLABLACOOK_SMTP_HOST est défini (identifiants lus dans l'environnement, jamais dans le code) ;
- console, sinon : le mail est affiché dans le terminal du serveur, pratique en développement.
Tous les transports gardent les derniers mails dans `outbox`, ce qui permet aux tests de lire le code reçu.
"""
import html as markup
import logging
import os
import smtplib
import ssl
from collections import deque
from email.message import EmailMessage

log = logging.getLogger("blablacook.mail")


class Mailer:
    def __init__(self):
        self.outbox = deque(maxlen=50)

    def send(self, to, subject, text, html=None):
        msg = EmailMessage()
        msg["To"], msg["Subject"] = to, subject
        msg["From"] = self.sender
        msg.set_content(text)
        if html:
            msg.add_alternative(html, subtype="html")
        self.outbox.append({"to": to, "subject": subject, "text": text})
        self.deliver(msg)

    sender = "BlablaCook <no-reply@blablacook.local>"

    def deliver(self, msg):
        raise NotImplementedError


class ConsoleMailer(Mailer):
    """Affiche le mail dans le terminal au lieu de l'envoyer."""

    def __init__(self, echo=True):
        super().__init__()
        self.echo = echo

    def deliver(self, msg):
        if self.echo:
            body = msg.get_body(("plain",)).get_content()
            print(f"\n--- Mail (mode console, aucun envoi réel) ---\nÀ : {msg['To']}\nObjet : {msg['Subject']}\n\n{body}---", flush=True)


class SmtpMailer(Mailer):
    def __init__(self, host, port, user, password, sender, security):
        super().__init__()
        self.host, self.port, self.user, self.password = host, port, user, password
        self.sender, self.security = sender, security

    def deliver(self, msg):
        context = ssl.create_default_context()
        try:
            if self.security == "ssl":
                server = smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=15)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                if self.security == "starttls":
                    server.starttls(context=context)
            with server:
                if self.user:
                    server.login(self.user, self.password)
                server.send_message(msg)
        except (OSError, smtplib.SMTPException):
            # Ne jamais journaliser le mot de passe : seuls l'hôte et le destinataire apparaissent.
            log.exception("Échec de l'envoi SMTP via %s vers %s", self.host, msg["To"])


def mailer_from_env():
    host = os.getenv("BLABLACOOK_SMTP_HOST", "").strip()
    if not host:
        return ConsoleMailer()
    security = os.getenv("BLABLACOOK_SMTP_SECURITY", "starttls").strip().lower()
    port = int(os.getenv("BLABLACOOK_SMTP_PORT") or (465 if security == "ssl" else 587))
    user = os.getenv("BLABLACOOK_SMTP_USER", "")
    sender = os.getenv("BLABLACOOK_MAIL_FROM") or user or "no-reply@blablacook.local"
    return SmtpMailer(host, port, user, os.getenv("BLABLACOOK_SMTP_PASSWORD", ""), sender, security)


def verification_mail(name, code, link):
    text = (f"Bonjour {name},\n\n"
            f"Bienvenue sur BlablaCook ! Pour activer ton compte, saisis ce code dans l'application :\n\n"
            f"    {code}\n\n"
            f"ou ouvre ce lien :\n{link}\n\n"
            "Le code et le lien sont valables 24 heures. Si tu n'es pas à l'origine de cette inscription, ignore ce mail.\n")
    safe, href = markup.escape(name), markup.escape(link)
    html = (f"<p>Bonjour {safe},</p><p>Bienvenue sur BlablaCook ! Pour activer ton compte, saisis ce code :</p>"
            f"<p style=\"font-size:24px;font-weight:bold;letter-spacing:4px\">{code}</p>"
            f"<p>ou <a href=\"{href}\">clique ici pour confirmer ton adresse</a>.</p>"
            "<p>Le code et le lien sont valables 24 heures.</p>")
    return "Confirme ton adresse étudiante BlablaCook", text, html
