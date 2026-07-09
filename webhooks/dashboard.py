"""Dashboard do dono: chamadas, urgências, marcações e recados numa página.

Servido pelo próprio serviço (GET /dashboard?token=...), sem dependências
externas — HTML gerado no servidor com os dados do SQLite + Cal.com.
Todos os dados de clientes passam por html.escape (vêm de conversas).
"""

import asyncio
import hmac
import html
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from .calcom import listar_marcacoes
from .config import get_settings
from .storage import dados_dashboard

router = APIRouter()

_JANELA_DIAS = 30

_CSS = """
:root { --tinta:#182032; --tinta2:#4a5468; --papel:#f4f5f8; --cartao:#fff;
  --linha:#d9dde6; --ambar:#b97a1e; --ambarf:#fdf3e3; --verde:#2e7d54;
  --verdef:#e8f4ed; --urg:#c4553f; --urgf:#fbeae6; --noite:#101623; }
@media (prefers-color-scheme: dark) {
  :root { --tinta:#e8ebf1; --tinta2:#9aa4b8; --papel:#0b0f18; --cartao:#151c2b;
    --linha:#29324a; --ambar:#e8a33d; --ambarf:#29231a; --verde:#58b98a;
    --verdef:#16281f; --urg:#e07a63; --urgf:#2e1c17; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--papel); color:var(--tinta);
  font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
.pg { max-width:1000px; margin:0 auto; padding:28px 20px 56px; }
h1 { font-size:22px; font-weight:750; letter-spacing:-.01em; margin:0; }
.sub { color:var(--tinta2); font-size:12.5px; margin:2px 0 0; }
h2 { font:600 11.5px ui-monospace,Menlo,monospace; letter-spacing:.14em;
  text-transform:uppercase; color:var(--ambar); margin:34px 0 12px;
  display:flex; align-items:center; gap:10px; }
h2::after { content:""; flex:1; height:1px; background:var(--linha); }
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
  gap:12px; margin-top:20px; }
.kpi { background:var(--cartao); border:1px solid var(--linha);
  border-radius:10px; padding:12px 14px; }
.kpi b { display:block; font:700 24px ui-monospace,Menlo,monospace;
  font-variant-numeric:tabular-nums; }
.kpi span { color:var(--tinta2); font-size:12px; }
.kpi.u b { color:var(--urg); } .kpi.m b { color:var(--verde); }
table { width:100%; border-collapse:collapse; background:var(--cartao);
  border:1px solid var(--linha); border-radius:10px; overflow:hidden; }
.rolar { overflow-x:auto; border-radius:10px; }
th,td { text-align:left; padding:9px 12px; border-bottom:1px solid var(--linha);
  vertical-align:top; font-size:13px; }
tr:last-child td { border-bottom:none; }
th { font:600 10.5px ui-monospace,Menlo,monospace; letter-spacing:.1em;
  text-transform:uppercase; color:var(--tinta2); white-space:nowrap; }
.mono { font-family:ui-monospace,Menlo,monospace; font-variant-numeric:tabular-nums;
  white-space:nowrap; font-size:12.5px; }
.pill { display:inline-block; font:700 10px ui-monospace,Menlo,monospace;
  letter-spacing:.08em; text-transform:uppercase; border-radius:99px;
  padding:2px 8px; white-space:nowrap; }
.p-urg { background:var(--urgf); color:var(--urg); }
.p-marc { background:var(--verdef); color:var(--verde); }
.p-rec { background:var(--ambarf); color:var(--ambar); }
.p-cinza { background:var(--linha); color:var(--tinta2); }
details summary { cursor:pointer; color:var(--ambar); font-size:12px; }
details pre { white-space:pre-wrap; font-size:12px; color:var(--tinta2);
  background:var(--papel); border-radius:8px; padding:10px; margin:8px 0 0; }
.vazio { color:var(--tinta2); font-size:13px; padding:14px;
  background:var(--cartao); border:1px dashed var(--linha); border-radius:10px; }
.futura { font-weight:650; color:var(--verde); }
"""


def _pill_tipo(tipo: str | None) -> str:
    classes = {"urgencia": ("p-urg", "urgência"), "marcacao": ("p-marc", "marcação"),
               "recado": ("p-rec", "recado")}
    classe, rotulo = classes.get(tipo or "", ("p-cinza", tipo or "—"))
    return f'<span class="pill {classe}">{rotulo}</span>'


def _hora_local(iso: str | None, fuso: ZoneInfo) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).astimezone(fuso).strftime("%d/%m %H:%M")
    except ValueError:
        return iso


def _e(valor) -> str:
    return html.escape(str(valor)) if valor not in (None, "") else "—"


def _render(dados: dict, marcacoes: list[dict], fuso: ZoneInfo) -> str:
    agora = datetime.now(fuso).strftime("%d-%m-%Y %H:%M")
    partes = [f"""<!doctype html><html lang="pt"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="120">
<title>Dashboard — Arranjos Horizonte</title><style>{_CSS}</style></head><body><div class="pg">
<h1>📞 Atendimento fora de horas</h1>
<p class="sub">Últimos {_JANELA_DIAS} dias · atualizado {agora} · a página recarrega a cada 2 min</p>
<div class="kpis">
<div class="kpi"><b>{dados['n_chamadas']}</b><span>chamadas atendidas</span></div>
<div class="kpi u"><b>{dados['n_urgencias']}</b><span>urgências acionadas</span></div>
<div class="kpi m"><b>{len([m for m in marcacoes if m['futura']])}</b><span>visitas agendadas</span></div>
<div class="kpi"><b>{dados['n_recados']}</b><span>recados a devolver</span></div>
<div class="kpi"><b>${dados['custo_total_usd']:.2f}</b><span>custo da plataforma</span></div>
</div>"""]

    # urgências
    partes.append("<h2>Urgências</h2>")
    if dados["urgencias"]:
        linhas = "".join(
            f"<tr><td class='mono'>{_hora_local(u['criado_em'], fuso)}</td>"
            f"<td>{_e(u['nome'])}</td><td>{_e(u['problema'])}</td>"
            f"<td>{_e(u['morada'])}</td><td class='mono'>{_e(u['telemovel'])}</td>"
            f"<td>{'<span class=\"pill p-marc\">SMS enviado</span>' if u['sms_enviado'] else '<span class=\"pill p-urg\">SMS falhou</span>'}</td></tr>"
            for u in dados["urgencias"]
        )
        partes.append(f"<div class='rolar'><table><tr><th>Quando</th><th>Cliente</th><th>Problema</th><th>Morada</th><th>Contacto</th><th>Alerta</th></tr>{linhas}</table></div>")
    else:
        partes.append("<div class='vazio'>Sem urgências no período — boas notícias.</div>")

    # marcações (Cal.com)
    partes.append("<h2>Visitas marcadas (agenda Cal.com)</h2>")
    if marcacoes:
        linhas = "".join(
            f"<tr><td class='mono {'futura' if m['futura'] else ''}'>{_e(m['quando'])}</td>"
            f"<td>{_e(m['nome'])}</td><td class='mono'>{_e(m['contacto'])}</td>"
            f"<td>{_e(m['titulo'])}</td><td>{_e(m['estado'])}</td></tr>"
            for m in marcacoes
        )
        partes.append(f"<div class='rolar'><table><tr><th>Quando</th><th>Cliente</th><th>Contacto</th><th>Serviço</th><th>Estado</th></tr>{linhas}</table></div>")
    else:
        partes.append("<div class='vazio'>Sem marcações na agenda (ou Cal.com indisponível).</div>")

    # recados
    partes.append("<h2>Recados — contactar</h2>")
    if dados["recados"]:
        linhas = "".join(
            f"<tr><td class='mono'>{_hora_local(r['criado_em'], fuso)}</td>"
            f"<td>{_e(r['nome'])}</td><td class='mono'>{_e(r['telemovel'])}</td>"
            f"<td>{_e(r['assunto'])}</td></tr>"
            for r in dados["recados"]
        )
        partes.append(f"<div class='rolar'><table><tr><th>Quando</th><th>Cliente</th><th>Contacto</th><th>Assunto</th></tr>{linhas}</table></div>")
    else:
        partes.append("<div class='vazio'>Sem recados pendentes.</div>")

    # chamadas
    partes.append("<h2>Todas as chamadas</h2>")
    if dados["chamadas"]:
        linhas = []
        for c in dados["chamadas"]:
            dur = f"{(c['duration_ms'] or 0) // 1000}s" if c["duration_ms"] else "—"
            transcript = (
                f"<details><summary>ver conversa</summary><pre>{html.escape(c['transcript'])}</pre></details>"
                if c.get("transcript") else ""
            )
            linhas.append(
                f"<tr><td class='mono'>{_hora_local(c['started_at'], fuso)}</td>"
                f"<td class='mono'>{_e(c['from_number'])}</td>"
                f"<td>{_pill_tipo(c['tipo_pedido'])}</td>"
                f"<td>{_e(c['resumo'])}{transcript}</td>"
                f"<td class='mono'>{dur}</td></tr>"
            )
        partes.append(f"<div class='rolar'><table><tr><th>Quando</th><th>De</th><th>Tipo</th><th>Resumo</th><th>Dur.</th></tr>{''.join(linhas)}</table></div>")
    else:
        partes.append("<div class='vazio'>Ainda sem chamadas no período.</div>")

    partes.append("</div></body></html>")
    return "".join(partes)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(token: str = "") -> HTMLResponse:
    settings = get_settings()
    if not settings.report_token or not hmac.compare_digest(token, settings.report_token):
        raise HTTPException(status_code=403, detail="Token inválido")
    desde = (datetime.now(UTC) - timedelta(days=_JANELA_DIAS)).isoformat(timespec="seconds")
    dados, marcacoes = await asyncio.gather(
        asyncio.to_thread(dados_dashboard, settings.db_path, desde),
        listar_marcacoes(),
    )
    fuso = ZoneInfo(settings.timezone)
    return HTMLResponse(_render(dados, marcacoes, fuso))
