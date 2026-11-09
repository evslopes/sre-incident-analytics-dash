# ADR-0001: Governança Zero-NDA com Gerador Determinístico de Telemetria Sintética

- **Status:** Aceito
- **Data:** 2026-11-08
- **Contexto:** Motores reais de análise de sustentação Nível 3 (L3) e SRE processam bases sensíveis contendo nomes de clientes B2B, identificadores de contratos, filas operacionais e janelas internas de mudança (GMUD). Publicar dumps ou schemas corporativos violaria cláusulas de confidencialidade (NDA) e LGPD.
- **Decisão:** Projetar o repositório como uma implementação *clean-room* **100% livre de dados corporativos**, alimentada por um gerador estatístico determinístico (`sre_analytics.synthetic_generator`) com semente reproduzível (`seed=42`). O gerador modela seis microsserviços genéricos (`payment-gateway`, `ledger-core`, `identity-sso`, `document-pipeline`, `order-orchestrator`, `webhook-dispatcher`), distribuição log-normal realista para `MTTA`/`MTTR`, correlação de regressões pós-GMUD, concentração de Pareto `80/20` e fração realista de *backlog* ativo sem `resolved_at`.
- **Consequências:**
  - **Positivas:** Auditabilidade pública total da engenharia estatística, testes determinísticos em CI/CD sem fixtures binárias pesadas e risco zero de vazamento de PII/NDA.
  - **Trade-offs:** Para uso interno em empresas reais, o adaptador de ingestão CSV (`validate_and_prepare_incidents`) mapeia colunas do ITSM corporativo (Jira Service Management, ServiceNow, Redmine) para o contrato canônico `REQUIRED_COLUMNS`.
