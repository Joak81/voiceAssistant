"""Relatório diário às 8h (Europe/Lisbon) por email para o dono do negócio."""

import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.mime.text import MIMEText

from .config import get_settings
from .storage import dados_relatorio

log = logging.getLogger("voice-onboard.report")

_TIPOS = {
    "urgencia": "urgência",
    "marcacao": "marcação",
    "recado": "recado",
    "outro": "outro",
}


def gerar_relatorio(db_path: str, desde_iso: str | None = None) -> str:
    """Compila o relatório das últimas 24h em texto simples PT-PT."""
    settings = get_settings()
    if desde_iso is None:
        desde_iso = (datetime.now(UTC) - timedelta(hours=24)).isoformat(
            timespec="seconds"
        )
    dados = dados_relatorio(db_path, desde_iso)
    hoje = datetime.now(UTC).strftime("%d-%m-%Y")
    linhas = [
        f"Relatório diário — {settings.business_name} — {hoje}",
        "",
        f"Chamadas atendidas: {dados['n_chamadas']}",
        f"Urgências acionadas: {dados['n_urgencias']}",
        f"Marcações feitas: {dados['n_marcacoes']}",
        f"Recados registados: {dados['n_recados']}",
        f"Custo estimado da plataforma: ${dados['custo_total_usd']:.2f}",
    ]
    if dados["urgencias"]:
        linhas += ["", "— Urgências —"]
        for u in dados["urgencias"]:
            estado = "SMS enviado" if u["sms_enviado"] else "SMS FALHOU"
            linhas.append(
                f"* {u['nome']} | {u['morada']} | {u['telemovel']} | "
                f"{u['problema']} [{estado}]"
            )
    if dados["recados"]:
        linhas += ["", "— Recados (contactar hoje) —"]
        for r in dados["recados"]:
            linhas.append(f"* {r['nome']} | {r['telemovel']} | {r['assunto']}")
    if dados["chamadas"]:
        linhas += ["", "— Resumo das chamadas —"]
        for c in dados["chamadas"]:
            resumo = c["resumo"] or "(sem resumo)"
            tipo = _TIPOS.get(c["tipo_pedido"] or "", c["tipo_pedido"] or "?")
            linhas.append(f"* [{tipo}] {c['from_number'] or '?'}: {resumo}")
    return "\n".join(linhas)


def enviar_email(assunto: str, corpo: str) -> bool:
    settings = get_settings()
    if not (settings.gmail_user and settings.gmail_app_password and settings.owner_email):
        log.warning("Email não configurado — relatório não enviado.")
        return False
    msg = MIMEText(corpo, "plain", "utf-8")
    msg["Subject"] = assunto
    msg["From"] = settings.gmail_user
    msg["To"] = settings.owner_email
    try:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.login(settings.gmail_user, settings.gmail_app_password)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as erro:
        log.error("Falha no envio do relatório: %s", erro)
        return False


def job_relatorio_diario() -> None:
    """Corre às report_hour (Europe/Lisbon), agendado pelo APScheduler."""
    settings = get_settings()
    corpo = gerar_relatorio(settings.db_path)
    hoje = datetime.now(UTC).strftime("%d-%m-%Y")
    if enviar_email(f"Relatório de chamadas — {hoje}", corpo):
        log.info("Relatório diário enviado para %s", settings.owner_email)
