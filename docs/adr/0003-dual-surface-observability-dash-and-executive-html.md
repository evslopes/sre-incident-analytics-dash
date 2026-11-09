# ADR-0003: Arquitetura de Dupla Superfície — Console Interativo Dash + Relatório Executivo HTML Autônomo

- **Status:** Aceito
- **Data:** 2026-11-08
- **Contexto:** Times de SRE e Sustentação L3 possuem duas audiências distintas: (a) engenheiros investigando causas-raiz que precisam filtrar dinamicamente janelas temporais, serviços, severidades e correlação GMUD; e (b) lideranças executivas / comitês semanais de SLA e Six Sigma que exigem um artefato autocontido de *Data Storytelling* enviável sem depender de servidor ativo.
- **Decisão:** Compartilhar os mesmos motores puros de domínio (`schema.py`, `kpi_engine.py`, `figures.py`) entre duas superfícies desacopladas:
  1. **Console Reativo (`app.py` / Gunicorn + Plotly Dash):** Filtros multidimensionais em tempo real e tabela *drill-down* de assinaturas crônicas.
  2. **Exportador Executivo Zero-Server (`report_exporter.py` / CLI `export-report`):** Gera um único arquivo HTML estático com KPIs, os 4 visuais interativos Plotly e recomendações priorizadas (`P0` Pareto, `P1` GMUD Gate, `P2` Runbooks L3).
- **Consequências:** Zero duplicação de fórmulas de SLA/Pareto entre o painel ao vivo e os relatórios gerenciais de governança.
