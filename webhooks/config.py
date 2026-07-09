"""Configuração do serviço — tudo vem de variáveis de ambiente / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Retell
    retell_api_key: str = ""
    verify_signature: bool = True  # desligar apenas em dev local

    # Twilio (SMS de urgência para o dono)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""  # número Twilio em formato E.164
    owner_phone: str = ""  # telemóvel do dono do negócio (+351...)

    # Relatório diário por email (Gmail SMTP com app password)
    gmail_user: str = ""
    gmail_app_password: str = ""
    owner_email: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    report_hour: int = 8
    timezone: str = "Europe/Lisbon"
    report_token: str = ""  # exigido no endpoint /relatorio/hoje

    # Cal.com (dashboard: listar marcações reais)
    calcom_api_key: str = ""

    # Negócio (usado nos textos de SMS/relatório)
    business_name: str = "Arranjos Horizonte"

    # Base de dados
    db_path: str = "data/voice.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
