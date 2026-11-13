import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

open_meteo_requests_total = Counter(
    "open_meteo_requests_total", "Chamadas ao Open-Meteo", ["resultado"]
)
http_requests_total = Counter(
    "http_requests_total", "Requisicoes HTTP", ["method", "route", "status"]
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Duracao das requisicoes",
    ["method", "route"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
http_requests_in_progress = Gauge("http_requests_in_progress", "Requisicoes em andamento")


def registrar_chamada_clima(resultado: str) -> None:
    open_meteo_requests_total.labels(resultado=resultado).inc()


def instalar_metricas(app) -> None:
    @app.middleware("http")
    async def coletar(request, call_next):
        inicio = time.perf_counter()
        http_requests_in_progress.inc()
        status = "500"
        try:
            resposta = await call_next(request)
            status = str(resposta.status_code)
            return resposta
        finally:
            rota = getattr(request.scope.get("route"), "path", "nao_mapeada")
            http_requests_total.labels(request.method, rota, status).inc()
            http_request_duration_seconds.labels(request.method, rota).observe(
                time.perf_counter() - inicio
            )
            http_requests_in_progress.dec()

    async def metricas(request):
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.add_route("/metrics", metricas, methods=["GET"])
