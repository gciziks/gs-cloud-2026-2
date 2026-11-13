"""Desenha os componentes implantados para o relatório."""

from pathlib import Path

import pymupdf as fitz
from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors

DESTINO = Path(__file__).resolve().parents[1] / "docs/img"
DESTINO.mkdir(parents=True, exist_ok=True)
d = Drawing(1000, 640)
azul = colors.HexColor("#075985")
cinza = colors.HexColor("#475569")


def caixa(x, y, w, h, titulo, subtitulo=""):
    d.add(Rect(x, y, w, h, rx=8, ry=8, fillColor=colors.HexColor("#f1f5f9"), strokeColor=azul))
    d.add(String(x + w / 2, y + h / 2 + (6 if subtitulo else -4), titulo,
                 fontName="Helvetica-Bold", fontSize=16, textAnchor="middle", fillColor=azul))
    if subtitulo:
        d.add(String(x + w / 2, y + h / 2 - 13, subtitulo,
                     fontSize=12, textAnchor="middle", fillColor=cinza))


def seta(x1, y1, x2, y2, rotulo=""):
    d.add(Line(x1, y1, x2, y2, strokeColor=cinza, strokeWidth=1.4))
    if x1 == x2:
        sinal = 1 if y2 > y1 else -1
        pontos = [x2, y2, x2 - 4, y2 - sinal * 8, x2 + 4, y2 - sinal * 8]
    else:
        sinal = 1 if x2 > x1 else -1
        pontos = [x2, y2, x2 - sinal * 8, y2 - 4, x2 - sinal * 8, y2 + 4]
    d.add(Polygon(pontos, fillColor=cinza, strokeColor=cinza))
    if rotulo:
        d.add(String(x1 + 8 if x1 == x2 else (x1 + x2) / 2,
                     (y1 + y2) / 2 + 7, rotulo, fontSize=10,
                     textAnchor="start" if x1 == x2 else "middle", fillColor=cinza))


d.add(Rect(210, 230, 570, 380, rx=12, ry=12, fillColor=colors.HexColor("#f0f9ff"),
           strokeColor=azul, strokeWidth=1.5))
d.add(String(230, 585, "AZURE | NORTH CENTRAL US", fontName="Helvetica-Bold",
             fontSize=15, fillColor=azul))
d.add(Rect(230, 260, 530, 270, rx=8, ry=8, fillColor=colors.white, strokeColor=cinza))
d.add(String(425, 315, "VM Ubuntu / Docker Compose", fontSize=13, fillColor=cinza))
d.add(String(425, 294, "NSG: 80 e 443. Sem SSH.", fontSize=13, fillColor=cinza))
caixas = [
    (15, 395, 150, 65, "Navegador", "HTTPS publico"),
    (250, 390, 130, 65, "Caddy", "TLS + token"),
    (425, 390, 140, 65, "FastAPI", "uid 10001"),
    (615, 390, 125, 65, "PostgreSQL", "volume local"),
    (250, 285, 150, 55, "node-exporter", "rede interna"),
    (250, 540, 150, 35, "ACR Basic", ""),
    (425, 540, 150, 35, "Key Vault", ""),
    (820, 540, 160, 55, "Storage state", "Brazil South"),
    (820, 390, 160, 65, "Open-Meteo", "previsao real"),
    (410, 130, 190, 65, "GitHub Actions", "scanners + OIDC"),
    (20, 130, 175, 65, "Prometheus local", "scrape autenticado"),
    (20, 25, 175, 65, "Grafana local", "4 sinais + alertas"),
    (245, 25, 140, 65, "ntfy", "notificacao"),
    (805, 130, 175, 65, "Terraform", "CLI do operador"),
]
for valores in caixas:
    caixa(*valores)
for valores in [(165,427,250,427,"443"), (380,427,425,427,""),
                 (565,427,615,427,""),
                 (315,390,315,340,""),
                 (107,90,107,130,""), (195,57,245,57,""),
                 (500,195,500,260,"Run Command"), (805,163,740,260,"cria recursos"),
                 (325,540,440,455,"AcrPull"), (500,540,500,455,"identidade VM")]:
    seta(*valores)
for x1, y1, x2, y2 in [(565,440,585,440), (585,440,585,480), (585,480,900,480),
                       (195,175,220,175), (220,175,220,367), (220,367,315,367),
                       (890,195,790,215), (790,215,790,568)]:
    d.add(Line(x1,y1,x2,y2,strokeColor=cinza,strokeWidth=1.4))
seta(900,480,900,455,"HTTPS")
seta(315,367,315,390)
d.add(String(235, 351, "HTTPS + bearer", fontSize=10, fillColor=cinza))
seta(790,568,820,568)
for x1,y1,x2,y2 in [(410,163,202,163), (202,163,202,558), (202,558,250,558)]:
    d.add(Line(x1,y1,x2,y2,strokeColor=azul,strokeWidth=1.4,strokeDashArray=[4,3]))
d.add(Polygon([250,558,242,562,242,554],fillColor=azul,strokeColor=azul))
d.add(String(270, 174, "OIDC / AcrPush", fontSize=11, fillColor=azul))
d.add(String(415, 83, "Sem SSH. Segredos lidos na VM pelo Key Vault.", fontSize=11, fillColor=cinza))
d.add(String(415, 61, "State e tfvars fora do repositorio. Portas locais: 127.0.0.1.", fontSize=11,
             fillColor=cinza))
svg = DESTINO / "arquitetura.svg"
for elemento in d.contents:
    if isinstance(elemento, String) and elemento.fontName == "Times-Roman":
        elemento.fontName = "Helvetica"
renderSVG.drawToFile(d, str(svg))
conteudo = svg.read_text(encoding="utf-8")
conteudo = conteudo.replace("<title>...</title>", "<title>Arquitetura do Vigia da Chuva</title>", 1)
conteudo = conteudo.replace("<desc>...</desc>", "<desc>VM Azure em North Central US, state em Brazil South, pipeline GitHub Actions e monitoramento local.</desc>", 1)
svg.write_text(conteudo, encoding="utf-8")
documento = fitz.open(stream=svg.read_bytes(), filetype="svg")
pdf = fitz.open("pdf", documento.convert_to_pdf())
pdf[0].get_pixmap(matrix=fitz.Matrix(2, 2)).save(DESTINO / "arquitetura.png")
print("Diagrama exportado em SVG e PNG.")
