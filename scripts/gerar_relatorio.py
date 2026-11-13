"""Gera o PDF a partir do relatório, imagens e execuções verificadas."""

import html
import json
import re
from pathlib import Path

import pymupdf
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, Preformatted,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
LARGURA = 174 * mm
azul = colors.HexColor("#075985")
estilos = getSampleStyleSheet()
estilos.add(ParagraphStyle("Corpo", fontName="Helvetica", fontSize=10.5, leading=15,
                          spaceAfter=9, textColor=colors.HexColor("#172b3a")))
estilos.add(ParagraphStyle("TituloDocumento", fontName="Helvetica-Bold", fontSize=30,
                          leading=37, spaceAfter=20, textColor=azul))
estilos.add(ParagraphStyle("SecaoDocumento", fontName="Helvetica-Bold", fontSize=19,
                          leading=24, spaceAfter=15, textColor=azul))
estilos.add(ParagraphStyle("Celula", fontName="Helvetica", fontSize=8.8, leading=12))
estilos.add(ParagraphStyle("CabecalhoTabela", parent=estilos["Celula"],
                          fontName="Helvetica-Bold", textColor=colors.white))
estilos.add(ParagraphStyle("LegendaDocumento", fontSize=9, leading=13,
                          textColor=colors.HexColor("#475569"), spaceAfter=14,
                          alignment=TA_CENTER))
estilos.add(ParagraphStyle("CodigoDocumento", fontName="Courier", fontSize=7.5,
                          leading=10, backColor=colors.HexColor("#f1f5f9"),
                          leftIndent=6, rightIndent=6, spaceAfter=12))


def formatar(texto):
    texto = html.escape(texto)
    texto = re.sub(r"\[([^]]+)\]\(([^)]+)\)",
                   lambda m: '<link color="#075985" href="' + m[2] + '">' + m[1] + '</link>', texto)
    texto = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", texto)
    return texto


def paragrafo(texto, estilo="Corpo"):
    return Paragraph(formatar(texto), estilos[estilo])


def tabela(linhas):
    n = len(linhas[0])
    proporcoes = {2: [.26, .74], 3: [.22, .39, .39],
                 4: [.18, .34, .27, .21], 5: [.27, .20, .15, .19, .19]}.get(n, [1/n]*n)
    celulas = [[paragrafo(c, "CabecalhoTabela" if i == 0 else "Celula")
                for c in linha] for i, linha in enumerate(linhas)]
    t = Table(celulas, colWidths=[LARGURA*p for p in proporcoes], repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), azul),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, 0), .5, azul),
    ]))
    return [t, Spacer(1, 12)]


def rodape(canvas, documento):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(18*mm, 16*mm, 192*mm, 16*mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(18*mm, 11*mm, "Vigia da Chuva | Cloud Computing | 2026.2")
    canvas.drawRightString(192*mm, 11*mm, str(documento.page))
    canvas.restoreState()


linhas = (DOCS / "relatorio.md").read_text(encoding="utf-8").splitlines()
historia = []
i = 0
while i < len(linhas):
    linha = linhas[i].strip()
    if not linha:
        i += 1
        continue
    if linha.startswith("# "):
        historia.extend([Spacer(1, 18*mm), paragrafo(linha[2:], "TituloDocumento")])
    elif linha.startswith("## "):
        historia.extend([PageBreak(), paragrafo(linha[3:], "SecaoDocumento")])
    elif linha.startswith("### "):
        historia.append(paragrafo(linha[4:], "Heading3"))
    elif linha.startswith("```"):
        codigo = []
        i += 1
        while i < len(linhas) and not linhas[i].startswith("```"):
            codigo.append(linhas[i])
            i += 1
        historia.append(Preformatted("\n".join(codigo), estilos["CodigoDocumento"], maxLineLength=95))
    elif linha.startswith("|"):
        dados = []
        while i < len(linhas) and linhas[i].strip().startswith("|"):
            if not re.match(r"^\|[\s:|-]+\|$", linhas[i].strip()):
                dados.append([c.strip() for c in linhas[i].strip().strip("|").split("|")])
            i += 1
        historia.extend(tabela(dados))
        continue
    elif linha.startswith("!["):
        m = re.fullmatch(r"!\[([^]]*)\]\(([^)]+)\)", linha)
        caminho = DOCS / m[2]
        if not caminho.exists():
            raise FileNotFoundError(f"Evidência ausente: {caminho.name}")
        pix = pymupdf.Pixmap(str(caminho))
        limite_altura = 150 * mm
        escala = min(LARGURA / pix.width, limite_altura / pix.height)
        imagem = Image(str(caminho), width=pix.width*escala, height=pix.height*escala)
        historia.append(KeepTogether([Spacer(1, 8), imagem, Spacer(1, 5),
                                      paragrafo(m[1], "LegendaDocumento")]))
    elif linha.startswith("- "):
        historia.append(paragrafo("• " + linha[2:]))
    else:
        texto = [linha]
        while i+1 < len(linhas) and linhas[i+1].strip() and not linhas[i+1].startswith(("#", "|", "!", "```", "- ")):
            i += 1
            texto.append(linhas[i].strip())
        historia.append(paragrafo(" ".join(texto)))
    i += 1

execucoes = json.loads((DOCS / "execucoes.json").read_text(encoding="utf-8"))
obrigatorias = {"gitleaks_corrigido", "semgrep_barrado", "semgrep_corrigido", "rollback", "producao_final"}
if not obrigatorias.issubset(execucoes):
    raise ValueError("A matriz de execuções ainda não está completa")
historia.extend([PageBreak(), paragrafo("Matriz de execuções", "SecaoDocumento")])
historia.append(paragrafo("Links clicáveis das execuções verificadas. As demonstrações inseguras não foram incorporadas à main."))
for nome, item in execucoes.items():
    historia.append(paragrafo(f"[{nome.replace('_', ' ')}]({item['url']}): {item['conclusion']}"))

arquivo = DOCS / "relatorio.pdf"
pdf = SimpleDocTemplate(str(arquivo), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                        topMargin=18*mm, bottomMargin=23*mm,
                        title="Vigia da Chuva - Cloud Computing", author="Cassio Valezzi; Gabriel Ciziks; Lucca Sabatini Tambellini; Victor Nuzzi")
pdf.build(historia, onFirstPage=rodape, onLaterPages=rodape)
print(f"PDF gerado: {arquivo.name}")
