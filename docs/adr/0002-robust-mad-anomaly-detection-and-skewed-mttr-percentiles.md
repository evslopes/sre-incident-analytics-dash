# ADR-0002: Uso de Percentis (`P50`/`P90`/`P95`) e Modified Z-Score (`MAD`) em Vez de Média Gaussiana

- **Status:** Aceito
- **Data:** 2026-11-08
- **Contexto:** Tempos de resolução de incidentes (`MTTR`) seguem distribuições fortemente assimétricas à direita (*log-normal* / cauda longa), e séries diárias de volume de chamados sofrem *masking* estatístico quando um grande incidente pós-GMUD infla artificialmente a média ($\mu$) e o desvio-padrão ($\sigma$).
- **Decisão:**
  1. Reportar sistematicamente `MTTR` por **percentis (`P50`, `P90`, `P95`)** em vez de média aritmética simples.
  2. Detectar anomalias diárias de volume pelo **Modified Z-Score baseado em MAD (*Median Absolute Deviation*)**:
     $$M_i = \frac{0.6745 \cdot (x_i - \tilde{x})}{\text{MAD}}$$
     sinalizando picos operacionais quando $M_i > 3.5$, com *fallback* automático para escala interquartil (`IQR / 1.349`) caso $\text{MAD} = 0$.
  3. Tratar explicitamente valores ausentes sem *data leakage*: chamados abertos preservam `mttr_hours = NaN` mas têm conformidade de SLA avaliada contra o tempo decorrido (`reference_now - opened_at`), enquanto ausências pontuais de `acknowledged_at` recebem imputação pela mediana da severidade com flag auditável `ack_imputed = True`.
- **Consequências:** Detecção resiliente de regressões pós-deploy sem falsos negativos causados por *outliers* extremos e preservação fiel do *backlog* em aberto.
