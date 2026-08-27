# 🗺️ Longevus — Análise Geoespacial do SUS no Sudoeste do Paraná

> TCC — André Luiz Costa da Silva  
> Análise Geoespacial dos Padrões de Utilização dos Serviços de Saúde Pública no Sudoeste do Paraná a partir de Dados Abertos

## Sobre o Projeto

O **Longevus** é uma plataforma de análise geoespacial de dados de saúde pública (SIH/SUS). Transforma dados brutos em arquivos `.dbc` em informações estratégicas visualizadas através de mapas interativos, permitindo a análise de padrões de utilização de saúde no Sudoeste do Paraná.

## Arquitetura

```
[DATASUS .dbc] → [Pipeline Python] → [PostgreSQL/PostGIS (Supabase)]
                                              ↓
                                    [API Node.js/Fastify]
                                              ↓
                                  [Frontend React + Leaflet]
```

## Estrutura do Repositório

```
longevus/
├── spec/                    # Especificações SDD
│   ├── requirements.md      # Requisitos funcionais e não-funcionais
│   ├── architecture.md      # Arquitetura do sistema
│   ├── data-model.md        # Modelos de dados e domínio
│   ├── api-spec.md          # Contratos da API
│   └── behaviors/           # Cenários BDD (Gherkin)
├── pipeline/                # Scripts Python (ETL)
├── backend/                 # API Node.js/Fastify
├── frontend/                # React + Vite + Leaflet
└── docs/                    # Documentação acadêmica
```

## Metodologia de Desenvolvimento

Este projeto adota **Specification-Driven Development (SDD)**:  
1. Especificação formal antes da implementação  
2. Implementação guiada pela spec  
3. Testes validados contra a spec  

## Tecnologias

| Camada | Tecnologia |
|--------|------------|
| ETL | Python (pysus, pandas) |
| Banco de Dados | PostgreSQL + PostGIS (container local via docker-compose; Supabase em nuvem) |
| Backend | Node.js + Fastify |
| Frontend | React + Vite + Leaflet + TanStack Query |
| Cache | node-cache (in-memory) |
| GeoJSON | IBGE — malha municipal |
