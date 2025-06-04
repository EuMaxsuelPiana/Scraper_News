# 📰 NotíciaScraper

Este repositório contém scripts em Python que realizam scraping de notícias de forma automática:

## 🔧 1. Scraper Avançado e Configurável

Um scraper robusto que:

- Coleta **título, link, resumo, data** e **(opcionalmente) conteúdo completo** das notícias.
- Suporta múltiplos sites configuráveis (ex: G1, sites fictícios).
- Evita duplicatas utilizando **hashes locais** das notícias processadas.
- Utiliza táticas anti-bloqueio: **headers customizados**, **retries com backoff** e **delays aleatórios**.
- Permite exportação para **JSON** ou **CSV**.
- Fácil de adaptar para novos sites alterando apenas a configuração.

### 💡 Exemplo de uso

```bash
python ...
