from webhooks.security import assinar, verificar_assinatura

KEY = "key_teste_1234567890"


def test_assinatura_valida():
    corpo = '{"event":"call_analyzed"}'
    assinatura = assinar(corpo, KEY)
    assert verificar_assinatura(corpo, KEY, assinatura)


def test_assinatura_corpo_alterado():
    assinatura = assinar('{"a":1}', KEY)
    assert not verificar_assinatura('{"a":2}', KEY, assinatura)


def test_assinatura_chave_errada():
    corpo = '{"a":1}'
    assinatura = assinar(corpo, "outra_chave")
    assert not verificar_assinatura(corpo, KEY, assinatura)


def test_assinatura_formato_invalido():
    assert not verificar_assinatura("{}", KEY, "lixo")
    assert not verificar_assinatura("{}", KEY, "")


def test_assinatura_expirada():
    corpo = "{}"
    ha_dez_minutos = 10 * 60 * 1000
    import time

    antiga = assinar(corpo, KEY, timestamp_ms=int(time.time() * 1000) - ha_dez_minutos)
    assert not verificar_assinatura(corpo, KEY, antiga)
