"""Carrega o system prompt do agente com as dynamic variables substituídas."""

import json
import re
from functools import lru_cache
from pathlib import Path

from .config import get_settings


@lru_cache
def carregar_prompt() -> tuple[str, str]:
    """Devolve (system_prompt, abertura_compliance), com {{vars}} resolvidas."""
    settings = get_settings()
    prompt = Path(settings.prompt_path).read_text()
    variables = json.loads(Path(settings.variables_path).read_text())
    for nome, valor in variables.items():
        prompt = prompt.replace("{{" + nome + "}}", str(valor))
    por_substituir = sorted(set(re.findall(r"{{(\w+)}}", prompt)))
    if por_substituir:
        raise ValueError(f"variáveis sem valor: {por_substituir}")
    abertura = (
        f"{variables['nome_empresa']}, boa noite. Sou a {variables['nome_agente']}, "
        "a assistente virtual da empresa. Esta chamada é atendida por inteligência "
        "artificial e pode ser gravada para garantir o seu atendimento. "
        "Em que posso ajudar?"
    )
    return prompt, abertura
