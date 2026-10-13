"""
setup_projeto.py — Monta a pasta do projeto "Captação × capacidade técnica" e
faz o inventário dos arquivos baixados do Transferegov e do Portal da Transparência.

Uso:
    python setup_projeto.py criar   [--raiz CAMINHO]   # passo 1: cria pastas, README e modelos
    python setup_projeto.py inventario [--raiz CAMINHO] # passo 4: lê tudo em data/raw e gera o inventário

Requisitos: Python 3.10+ e pandas  (pip install pandas pyarrow)
"""
import argparse, csv, datetime as dt, hashlib, io, sys, zipfile
from pathlib import Path

PASTAS = [
    "data/raw/transferegov_discricionarias",   # CSVs de convênios/propostas/emendas (download manual)
    "data/raw/transferegov_especiais",         # transferências especiais (emenda Pix)
    "data/raw/transparencia_emendas",          # Portal da Transparência: emendas (todas as modalidades)
    "data/raw/ibge_munic",                     # MUNIC/IBGE: recursos humanos municipais
    "data/interim", "data/processed",
    "docs", "src", "notebooks", "outputs/figuras", "outputs/tabelas",
]

README = """# Captação de recursos × capacidade técnica municipal

**Pergunta:** a expansão das emendas impositivas e das transferências especiais reduziu ou ampliou
a desigualdade de captação entre municípios com alta e baixa capacidade técnica?

**Período:** 2015–2025 · **Unidade:** município (código IBGE de 7 dígitos)

## Regras da pasta
- `data/raw/` é **imutável**: nunca editar um arquivo baixado. Cada download fica numa subpasta com a data (AAAA-MM-DD).
- Todo download é registrado em `docs/log_downloads.csv` (fonte, URL, data, arquivo, hash).
- Limpeza gera arquivos em `data/interim/`; bases prontas para análise ficam em `data/processed/`.
- `data/` não vai para o GitHub (ver `.gitignore`); o código e os `docs/` vão.

## Decisões registradas
| Data | Decisão | Motivo |
|---|---|---|
| {hoje} | Ano de referência do convênio = ano de assinatura | A proposta pode levar mais de um ano até virar convênio |
| {hoje} | Guardar também as propostas (aprovadas e rejeitadas) | Taxa de aprovação é um bom indicador de capacidade técnica |
| {hoje} | Emendas vêm do Portal da Transparência, não só do Transferegov | Parte das emendas (ex.: saúde, fundo a fundo) não passa por convênio |

## Fontes
Ver `docs/fontes.md`.
"""

FONTES = """# Fontes de dados

| Base | Onde baixar | O que contém | Pasta |
|---|---|---|---|
| Transferegov — Discricionárias e Legais | https://api-publica.transferegov.gestao.gov.br/downloads | Propostas, convênios, contratos de repasse, emendas vinculadas, pagamentos | data/raw/transferegov_discricionarias |
| Transferegov — Transferências Especiais | https://api-publica.transferegov.gestao.gov.br/especiais | Planos de ação das transferências especiais (emenda Pix) | data/raw/transferegov_especiais |
| Portal da Transparência — Emendas | https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares | Emendas por autor, função, localidade e execução | data/raw/transparencia_emendas |
| IBGE — MUNIC | https://www.ibge.gov.br/estatisticas/sociais/saude/10586-pesquisa-de-informacoes-basicas-municipais.html | Recursos humanos e estrutura de gestão dos municípios | data/raw/ibge_munic |

Dúvidas sobre os dados do Transferegov: CGIMO.DTPAR@GESTAO.GOV.BR
"""

DICIONARIO = """# Dicionário de variáveis

Preencher depois do inventário (`docs/inventario_colunas.csv`).

| Variável final | Arquivo de origem | Coluna original | Tipo | Descrição | Observações |
|---|---|---|---|---|---|
| cod_ibge | | | texto (7) | Código IBGE do município proponente | |
| ano | | | inteiro | Ano de assinatura do convênio | |
| modalidade | | | categoria | convênio discricionário / emenda via convênio / transferência especial | |
| valor_global | | | número (R$) | Valor global pactuado, nominal | Deflacionar pelo IPCA na semana 2 |
| situacao | | | categoria | Situação do instrumento | |
"""

GITIGNORE = "data/\n*.zip\n*.parquet\n__pycache__/\n.ipynb_checkpoints/\n.venv/\n"

def criar(raiz: Path):
    hoje = dt.date.today().isoformat()
    for p in PASTAS:
        (raiz / p).mkdir(parents=True, exist_ok=True)
    arquivos = {
        "README.md": README.replace("{hoje}", hoje),
        "docs/fontes.md": FONTES,
        "docs/dicionario_variaveis.md": DICIONARIO,
        ".gitignore": GITIGNORE,
    }
    for nome, conteudo in arquivos.items():
        alvo = raiz / nome
        if not alvo.exists():
            alvo.write_text(conteudo, encoding="utf-8")
    log = raiz / "docs/log_downloads.csv"
    if not log.exists():
        log.write_text("data_download,fonte,url,arquivo,tamanho_mb,sha256\n", encoding="utf-8")
    print(f"Pasta do projeto pronta em: {raiz.resolve()}")
    print("Próximo passo: baixar os arquivos para as subpastas de data/raw/ (ver docs/fontes.md).")

def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()

def detectar_csv(amostra: bytes):
    """Descobre codificação e separador olhando o começo do arquivo."""
    corte = amostra.rfind(b"\n")
    amostra = amostra[:corte] if corte > 0 else amostra   # não cortar um caractere ao meio
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = amostra.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        sep = csv.Sniffer().sniff(texto.splitlines()[0], delimiters=";,|\t").delimiter
    except csv.Error:
        sep = ";"
    return enc, sep

def ler_cabecalho_e_contar(abrir):
    """abrir() devolve um stream binário novo. Retorna (encoding, sep, colunas, n_linhas)."""
    with abrir() as f:
        enc, sep = detectar_csv(f.read(200_000))
    with abrir() as f:
        texto = io.TextIOWrapper(f, encoding=enc, errors="replace", newline="")
        leitor = csv.reader(texto, delimiter=sep)
        colunas = next(leitor, [])
        n = sum(1 for _ in leitor)
    return enc, sep, colunas, n

def inventario(raiz: Path):
    raw = raiz / "data/raw"
    if not raw.exists():
        sys.exit("data/raw não existe. Rode primeiro: python setup_projeto.py criar")
    linhas_arq, linhas_col = [], []
    log_path = raiz / "docs/log_downloads.csv"
    ja_logados = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    novos_log = []
    for arq in sorted(raw.rglob("*")):
        if not arq.is_file():
            continue
        fonte = arq.relative_to(raw).parts[0]
        tamanho = arq.stat().st_size / 1e6
        hash_ = sha256(arq)
        if hash_ not in ja_logados:
            novos_log.append([dt.date.today().isoformat(), fonte, "PREENCHER_URL", str(arq.relative_to(raiz)), f"{tamanho:.1f}", hash_])
        alvos = []
        if arq.suffix.lower() == ".zip":
            with zipfile.ZipFile(arq) as z:
                for nome in z.namelist():
                    if nome.lower().endswith((".csv", ".txt")):
                        alvos.append((f"{arq.name}::{nome}", lambda z=arq, n=nome: zipfile.ZipFile(z).open(n)))
        elif arq.suffix.lower() in (".csv", ".txt"):
            alvos.append((arq.name, lambda a=arq: open(a, "rb")))
        else:
            linhas_arq.append([fonte, arq.name, f"{tamanho:.1f}", "", "", "", "", "não é CSV: abrir manualmente"])
            continue
        for nome, abrir in alvos:
            try:
                enc, sep, cols, n = ler_cabecalho_e_contar(abrir)
                linhas_arq.append([fonte, nome, f"{tamanho:.1f}", enc, repr(sep), len(cols), n, ""])
                for i, c in enumerate(cols, 1):
                    linhas_col.append([fonte, nome, i, c])
                print(f"[ok] {nome}: {n:,} linhas".replace(",", ".") + f", {len(cols)} colunas")
            except Exception as e:  # arquivo corrompido ou formato inesperado
                linhas_arq.append([fonte, nome, f"{tamanho:.1f}", "", "", "", "", f"erro: {e}"])
                print(f"[erro] {nome}: {e}")
    docs = raiz / "docs"
    with open(docs / "inventario_arquivos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["fonte", "arquivo", "tamanho_mb", "encoding", "separador", "n_colunas", "n_linhas", "obs"]); w.writerows(linhas_arq)
    with open(docs / "inventario_colunas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["fonte", "arquivo", "posicao", "coluna"]); w.writerows(linhas_col)
    if novos_log:
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(novos_log)
    print(f"\nInventário salvo em docs/inventario_arquivos.csv e docs/inventario_colunas.csv")
    if novos_log:
        print(f"{len(novos_log)} arquivo(s) novo(s) no docs/log_downloads.csv: preencha a coluna url.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["criar", "inventario"])
    ap.add_argument("--raiz", default="captacao-capacidade", help="pasta do projeto (padrão: ./captacao-capacidade)")
    a = ap.parse_args()
    raiz = Path(a.raiz)
    criar(raiz) if a.acao == "criar" else inventario(raiz)
