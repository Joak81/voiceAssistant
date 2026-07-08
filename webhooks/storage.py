"""Persistência em SQLite (volume do Railway em produção).

Funções síncronas e de vida curta — os endpoints chamam-nas via
asyncio.to_thread ou em background tasks. Timestamps em UTC ISO 8601.
"""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chamadas (
    call_id TEXT PRIMARY KEY,
    from_number TEXT,
    to_number TEXT,
    started_at TEXT,
    ended_at TEXT,
    duration_ms INTEGER,
    resumo TEXT,
    sentimento TEXT,
    sucesso INTEGER,
    voicemail INTEGER,
    tipo_pedido TEXT,
    custo_usd REAL,
    transcript TEXT,
    atualizado_em TEXT
);
CREATE INDEX IF NOT EXISTS idx_chamadas_started_at ON chamadas(started_at);
CREATE INDEX IF NOT EXISTS idx_chamadas_atualizado_em ON chamadas(atualizado_em);
CREATE TABLE IF NOT EXISTS urgencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT,
    nome TEXT,
    morada TEXT,
    telemovel TEXT,
    problema TEXT,
    sms_enviado INTEGER DEFAULT 0,
    criado_em TEXT
);
CREATE TABLE IF NOT EXISTS recados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT,
    nome TEXT,
    telemovel TEXT,
    assunto TEXT,
    criado_em TEXT
);
"""


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _ligar(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str) -> None:
    with _ligar(db_path) as conn:
        conn.executescript(_SCHEMA)


def guardar_urgencia(
    db_path: str, call_id: str, nome: str, morada: str, telemovel: str, problema: str
) -> int:
    with _ligar(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO urgencias (call_id, nome, morada, telemovel, problema, criado_em)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (call_id, nome, morada, telemovel, problema, _agora()),
        )
        return cur.lastrowid


def marcar_sms_enviado(db_path: str, urgencia_id: int) -> None:
    with _ligar(db_path) as conn:
        conn.execute("UPDATE urgencias SET sms_enviado = 1 WHERE id = ?", (urgencia_id,))


def guardar_recado(
    db_path: str, call_id: str, nome: str, telemovel: str, assunto: str
) -> int:
    with _ligar(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO recados (call_id, nome, telemovel, assunto, criado_em)"
            " VALUES (?, ?, ?, ?, ?)",
            (call_id, nome, telemovel, assunto, _agora()),
        )
        return cur.lastrowid


def _ms_para_iso(ms: int | None) -> str | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="seconds")


def upsert_chamada(db_path: str, call: dict) -> None:
    """Grava/atualiza uma chamada a partir do objeto call dos webhooks Retell."""
    call_id = call.get("call_id")
    if not call_id:
        return
    analise = call.get("call_analysis") or {}
    custo = (call.get("call_cost") or {}).get("combined_cost")
    dados_extra = analise.get("custom_analysis_data") or {}
    valores = {
        "from_number": call.get("from_number"),
        "to_number": call.get("to_number"),
        "started_at": _ms_para_iso(call.get("start_timestamp")),
        "ended_at": _ms_para_iso(call.get("end_timestamp")),
        "duration_ms": call.get("duration_ms"),
        "resumo": analise.get("call_summary"),
        "sentimento": analise.get("user_sentiment"),
        "sucesso": _para_int(analise.get("call_successful")),
        "voicemail": _para_int(analise.get("in_voicemail")),
        "tipo_pedido": dados_extra.get("tipo_pedido"),
        # combined_cost vem em cêntimos de dólar (unit price * duração)
        "custo_usd": custo / 100 if isinstance(custo, (int, float)) else None,
        "transcript": call.get("transcript"),
    }
    with _ligar(db_path) as conn:
        conn.execute(
            "INSERT INTO chamadas (call_id, atualizado_em) VALUES (?, ?)"
            " ON CONFLICT(call_id) DO NOTHING",
            (call_id, _agora()),
        )
        # só substitui campos que vieram preenchidos neste evento
        campos = {k: v for k, v in valores.items() if v is not None}
        if campos:
            sets = ", ".join(f"{k} = ?" for k in campos)
            conn.execute(
                f"UPDATE chamadas SET {sets}, atualizado_em = ? WHERE call_id = ?",
                (*campos.values(), _agora(), call_id),
            )


def _para_int(valor) -> int | None:
    if valor is None:
        return None
    return 1 if valor else 0


def dados_relatorio(db_path: str, desde_iso: str) -> dict:
    """Agrega a atividade desde o instante dado (para o relatório diário)."""
    with _ligar(db_path) as conn:
        # Janela pelo início da chamada (fallback: última atualização), para a mesma
        # chamada não aparecer em dois relatórios; sem transcript (o relatório não o usa).
        chamadas = [
            dict(r)
            for r in conn.execute(
                "SELECT call_id, from_number, to_number, started_at, ended_at,"
                " duration_ms, resumo, sentimento, sucesso, voicemail, tipo_pedido,"
                " custo_usd FROM chamadas"
                " WHERE COALESCE(started_at, atualizado_em) >= ?"
                " ORDER BY started_at",
                (desde_iso,),
            )
        ]
        urgencias = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM urgencias WHERE criado_em >= ? ORDER BY criado_em",
                (desde_iso,),
            )
        ]
        recados = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM recados WHERE criado_em >= ? ORDER BY criado_em",
                (desde_iso,),
            )
        ]
    custo_total = sum(c["custo_usd"] or 0 for c in chamadas)
    return {
        "chamadas": chamadas,
        "urgencias": urgencias,
        "recados": recados,
        "n_chamadas": len(chamadas),
        "n_urgencias": len(urgencias),
        "n_recados": len(recados),
        "n_marcacoes": sum(1 for c in chamadas if c["tipo_pedido"] == "marcacao"),
        "custo_total_usd": round(custo_total, 2),
    }


def raw_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)
