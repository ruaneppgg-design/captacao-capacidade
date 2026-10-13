# Captação de recursos × capacidade técnica municipal

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
| 2026-10-13 | Ano de referência do convênio = ano de assinatura | A proposta pode levar mais de um ano até virar convênio |
| 2026-10-13 | Guardar também as propostas (aprovadas e rejeitadas) | Taxa de aprovação é um bom indicador de capacidade técnica |
| 2026-10-13 | Emendas vêm do Portal da Transparência, não só do Transferegov | Parte das emendas (ex.: saúde, fundo a fundo) não passa por convênio |

## Fontes
Ver `docs/fontes.md`.
