import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .clima import ClienteClima, PrevisaoIndisponivel
from .config import Settings, get_settings
from .metricas import instalar_metricas
from .municipios import carregar_municipios
from .privacidade import hash_ip
from .relatos import (
    ErroValidacao,
    LimiteExcedido,
    RepositorioPostgres,
    Situacao,
    registrar,
    validar,
)
from .risco import avaliar

BASE = Path(__file__).parent
MUNICIPIOS = carregar_municipios(BASE / "dados/municipios.csv")
CAPITAIS = [
    1100205,
    1200401,
    1302603,
    1400100,
    1501402,
    1600303,
    1721000,
    2111300,
    2211001,
    2304400,
    2408102,
    2507507,
    2611606,
    2704302,
    2800308,
    2927408,
    3106200,
    3205309,
    3304557,
    3550308,
    4106902,
    4205407,
    4314902,
    5002704,
    5103403,
    5208707,
    5300108,
]
CAPITAIS = list(dict.fromkeys(CAPITAIS))
templates = Jinja2Templates(directory=str(BASE / "templates"))


def criar_app(
    settings: Settings | None = None,
    repo=None,
    clima=None,
    relogio: Callable[[], datetime] | None = None,
) -> FastAPI:
    configuracao = settings or get_settings()
    agora = relogio or (lambda: datetime.now(UTC))
    http = None

    @asynccontextmanager
    async def lifespan(app):
        nonlocal repo, clima, http
        owns_repo = repo is None
        if owns_repo:
            repo = await RepositorioPostgres.conectar(configuracao.database_url)
        if clima is None:
            http = httpx.AsyncClient(timeout=configuracao.timeout_upstream_segundos)
            clima = ClienteClima(
                http, configuracao.open_meteo_url, configuracao.cache_ttl_segundos, agora
            )

        async def retencao():
            while True:
                try:
                    await repo.aplicar_retencao(agora())
                except Exception:
                    logging.getLogger(__name__).exception("Falha na retenção dos relatos")
                await asyncio.sleep(60)

        await repo.aplicar_retencao(agora())
        tarefa = asyncio.create_task(retencao())
        app.state.repo, app.state.clima = repo, clima
        try:
            yield
        finally:
            tarefa.cancel()
            with suppress(asyncio.CancelledError):
                await tarefa
            if http:
                await http.aclose()
            if owns_repo:
                await repo.pool.close()

    app = FastAPI(lifespan=lifespan)
    # O compose não publica a porta da aplicação; Caddy sobrescreve o IP encaminhado.
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    instalar_metricas(app)
    app.state.repo, app.state.clima = repo, clima

    def contexto(request, **dados):
        return {
            "request": request,
            "agora": agora(),
            "capitais": [MUNICIPIOS[c] for c in CAPITAIS if c in MUNICIPIOS],
            **dados,
        }

    def pagina_erro(request, codigo=404):
        return templates.TemplateResponse(
            request, "erro.html", contexto(request, status=codigo), status_code=codigo
        )

    async def pagina_municipio(request, codigo, valores=None, erros=None, enviado=False):
        municipio = MUNICIPIOS.get(codigo)
        if municipio is None:
            return pagina_erro(request)
        previsao = None
        avaliacao = None
        try:
            previsao = await request.app.state.clima.previsao(municipio)
            avaliacao = avaliar(previsao.horas, agora())
        except PrevisaoIndisponivel:
            pass
        relatos = await request.app.state.repo.listar_recentes(
            codigo, agora() - timedelta(hours=24)
        )
        return templates.TemplateResponse(
            request,
            "municipio.html",
            contexto(
                request,
                municipio=municipio,
                previsao=previsao,
                avaliacao=avaliacao,
                zona=ZoneInfo(municipio.fuso),
                inicio_janela=agora() - timedelta(hours=1),
                fim_janela=agora() + timedelta(hours=24),
                relatos=relatos,
                valores=valores or {},
                erros=erros or {},
                enviado=enviado,
                situacoes=list(Situacao),
            ),
        )

    @app.get("/", response_class=HTMLResponse)
    async def inicio(request: Request):
        return templates.TemplateResponse(request, "inicio.html", contexto(request))

    @app.get("/buscar", response_class=HTMLResponse)
    async def busca(request: Request, q: str = ""):
        from .municipios import buscar

        resultados = buscar(MUNICIPIOS, q)
        return templates.TemplateResponse(
            request, "busca.html", contexto(request, q=q, resultados=resultados)
        )

    @app.get("/api/municipios")
    async def api_municipios(q: str = ""):
        from .municipios import buscar

        return [
            {"codigo_ibge": m.codigo_ibge, "nome": m.nome, "uf": m.uf}
            for m in buscar(MUNICIPIOS, q)
        ]

    @app.get("/municipio/{codigo}", response_class=HTMLResponse)
    async def municipio(request: Request, codigo: str, enviado: int = 0):
        if not codigo.isdigit() or int(codigo) not in MUNICIPIOS:
            return pagina_erro(request)
        return await pagina_municipio(request, int(codigo), enviado=bool(enviado))

    @app.post("/municipio/{codigo}/relatos")
    async def novo_relato(
        request: Request,
        codigo: str,
        bairro: str = Form(""),
        referencia: str = Form(""),
        situacao: str = Form(""),
        site: str = Form(""),
    ):
        if not codigo.isdigit() or int(codigo) not in MUNICIPIOS:
            return pagina_erro(request)
        try:
            novo = validar(
                {"bairro": bairro, "referencia": referencia, "situacao": situacao, "site": site},
                int(codigo),
            )
            ip = request.client.host if request.client else ""
            assinatura = hash_ip(
                ip, configuracao.ip_hash_secret.get_secret_value().encode(), agora().date()
            )
            await registrar(
                request.app.state.repo,
                novo,
                assinatura,
                agora(),
                configuracao.limite_relatos_por_hora,
            )
            return RedirectResponse(f"/municipio/{codigo}?enviado=1", status_code=303)
        except ErroValidacao as erro:
            return await pagina_municipio(
                request,
                int(codigo),
                {"bairro": bairro, "referencia": referencia, "situacao": situacao},
                erro.campos,
            )
        except LimiteExcedido:
            resposta = await pagina_municipio(request, int(codigo))
            resposta.status_code = 429
            return resposta

    @app.get("/api/municipios/{codigo}/previsao")
    async def api_previsao(request: Request, codigo: str):
        if not codigo.isdigit() or int(codigo) not in MUNICIPIOS:
            return JSONResponse({"detalhe": "município não encontrado"}, status_code=404)
        m = MUNICIPIOS[int(codigo)]
        try:
            p = await request.app.state.clima.previsao(m)
            a = avaliar(p.horas, agora())
        except PrevisaoIndisponivel:
            return JSONResponse({"detalhe": "previsao indisponivel"}, status_code=503)
        return {
            "municipio": {"codigo_ibge": m.codigo_ibge, "nome": m.nome, "uf": m.uf},
            "nivel": a.nivel.value,
            "max_mm_hora": a.max_mm_hora,
            "total_mm_24h": a.total_mm_24h,
            "hora_pico": a.hora_pico,
            "obtida_em": p.obtida_em,
            "desatualizada": p.desatualizada,
            "horas": [
                {
                    "inicio": h.inicio,
                    "precipitacao_mm": h.precipitacao_mm,
                    "probabilidade_pct": h.probabilidade_pct,
                }
                for h in p.horas
            ],
        }

    @app.get("/privacidade", response_class=HTMLResponse)
    async def privacidade(request: Request):
        return templates.TemplateResponse(request, "privacidade.html", contexto(request))

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(request: Request):
        try:
            ok = await request.app.state.repo.pronto()
        except Exception:
            ok = False
        return JSONResponse(
            {"status": "ok" if ok else "indisponivel"}, status_code=200 if ok else 503
        )

    @app.exception_handler(RequestValidationError)
    async def requisicao_invalida(request, exc):
        if request.url.path.startswith("/municipio/"):
            return pagina_erro(request)
        return JSONResponse({"detail": "requisição inválida"}, status_code=422)

    return app
