import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import random
import hashlib
import os
from urllib.parse import urljoin

CONFIG = {
    "g1": {
        "base_url": "https://g1.globo.com/",
        "news_item_selector": "div.feed-post-body",
        "title_selector": "a.feed-post-link",
        "link_selector": "a.feed-post-link",
        "summary_selector": "div.feed-post-body-resumo",
        "date_selector": "span._feed-post-datetime", # Seletor atualizado para G1 (pode precisar de ajuste)
        "content_selector": "article.mc-article", # Seletor mais específico para conteúdo no G1
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Referer": "https://www.google.com/"
        },
        "min_delay_seconds": 2,
        "max_delay_seconds": 5,
        "max_retries": 3,
        "backoff_factor": 0.5,
        "processed_hashes_file": "g1_processed_hashes.json" # Arquivo para guardar hashes processados
    },
    "example_site": {
        "base_url": "https://www.examplenews.com/",
        "news_item_selector": "article.news-item",
        "title_selector": "h2.news-title a",
        "link_selector": "h2.news-title a",
        "summary_selector": "p.news-summary",
        "date_selector": "span.publish-date",
        "content_selector": "div.article-content",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15"
        },
        "min_delay_seconds": 1,
        "max_delay_seconds": 4,
        "max_retries": 2,
        "backoff_factor": 0.3,
        "processed_hashes_file": "example_processed_hashes.json"
    }
}


def generate_news_hash(news_data):
    """Gera um hash SHA256 único para a notícia, baseado no link."""
    if news_data and news_data.get("link"):
        link = news_data["link"]
        return hashlib.sha256(link.encode("utf-8")).hexdigest()
    elif news_data and news_data.get("title"):
        title = news_data["title"]
        return hashlib.sha256(title.encode("utf-8")).hexdigest()
    return None

def load_processed_hashes(filename):
    """Carrega o conjunto de hashes de notícias já processadas de um arquivo JSON."""
    if not os.path.exists(filename):
        return set()
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (IOError, json.JSONDecodeError) as e:
        print(f"Erro ao carregar arquivo de hashes {filename}: {e}. Iniciando com conjunto vazio.")
        return set()

def save_processed_hashes(hashes_set, filename):
    """Salva o conjunto atualizado de hashes processados em um arquivo JSON."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(list(hashes_set), f, indent=4)
        print(f"Hashes processados salvos em {filename}")
    except IOError as e:
        print(f"Erro ao salvar arquivo de hashes {filename}: {e}")


def get_page_content(url, headers, max_retries=3, backoff_factor=0.3):
    """Busca o conteúdo HTML de uma URL com tratamento de erros, retries e backoff."""
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 5))
                wait_time = max(retry_after, backoff_factor * (2 ** retries))
                print(f"Recebido status 429. Aguardando {wait_time:.2f} segundos...")
                time.sleep(wait_time)
                retries += 1
                continue
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except requests.exceptions.HTTPError as e:
            if 500 <= e.response.status_code < 600:
                wait_time = backoff_factor * (2 ** retries)
                print(f"Erro HTTP {e.response.status_code} em {url}. Tentando novamente em {wait_time:.2f}s... ({retries + 1}/{max_retries})")
                time.sleep(wait_time)
                retries += 1
            else:
                print(f"Erro HTTP {e.response.status_code} (não recuperável) em {url}: {e}")
                return None
        except requests.exceptions.ConnectionError as e:
            wait_time = backoff_factor * (2 ** retries)
            print(f"Erro de conexão em {url}: {e}. Tentando novamente em {wait_time:.2f}s... ({retries + 1}/{max_retries})")
            time.sleep(wait_time)
            retries += 1
        except requests.exceptions.Timeout as e:
            wait_time = backoff_factor * (2 ** retries)
            print(f"Timeout em {url}: {e}. Tentando novamente em {wait_time:.2f}s... ({retries + 1}/{max_retries})")
            time.sleep(wait_time)
            retries += 1
        except requests.exceptions.RequestException as e:
            print(f"Erro geral de requisição em {url}: {e}")
            return None
        except Exception as e:
            print(f"Erro inesperado em {url}: {e}")
            return None
    print(f"Falha ao obter conteúdo de {url} após {max_retries} tentativas.")
    return None

def extract_news_data(html_content, config):
    """Extrai dados das notícias do HTML usando os seletores da configuração, com tratamento de erros."""
    if not html_content:
        return []
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        print(f"Erro ao parsear HTML: {e}")
        return []
    news_list = []
    try:
        news_items = soup.select(config["news_item_selector"])
        if not news_items:
             print(f"Aviso: Nenhum item encontrado com o seletor principal '{config['news_item_selector']}'.")
    except Exception as e:
        print(f"Erro ao selecionar itens de notícia com '{config['news_item_selector']}': {e}")
        return []
    print(f"Encontrados {len(news_items)} itens de notícia com o seletor '{config['news_item_selector']}'.")
    for i, item in enumerate(news_items):
        data = {"title": None, "link": None, "summary": None, "date": None, "full_content": None, "source_url": config["base_url"]}
        try:
            title_element = item.select_one(config["title_selector"])
            if title_element: data["title"] = title_element.get_text(strip=True)
            else: print(f"Aviso: Título não encontrado no item {i+1} usando seletor '{config['title_selector']}'.")
            link_element = item.select_one(config["link_selector"])
            if link_element and link_element.has_attr('href'): data["link"] = urljoin(config["base_url"], link_element['href'])
            else: print(f"Aviso: Link não encontrado no item {i+1} usando seletor '{config['link_selector']}'.")
            if config["summary_selector"]:
                summary_element = item.select_one(config["summary_selector"])
                if summary_element: data["summary"] = summary_element.get_text(strip=True)
            if config["date_selector"]:
                date_element = item.select_one(config["date_selector"])
                if date_element:
                    data["date"] = date_element.get_text(strip=True)
                    if date_element.has_attr('datetime'): data["date_iso"] = date_element['datetime']
                    elif date_element.has_attr('title'): data["date_raw"] = date_element['title']
            if data["title"] and data["link"]:
                news_list.append(data)
            else: print(f"Item {i+1} ignorado por falta de título ou link essenciais.")
        except Exception as e:
            print(f"Erro ao processar item de notícia {i+1}: {e}. Item: {str(item)[:200]}...")
            continue
    return news_list

def export_to_json(data, filename="noticias.json"):
    """Exporta a lista de dicionários para um arquivo JSON."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Dados exportados para {filename}")
    except IOError as e:
        print(f"Erro ao escrever arquivo JSON {filename}: {e}")

def export_to_csv(data, filename="noticias.csv"):
    """Exporta a lista de dicionários para um arquivo CSV."""
    if not data:
        print("Nenhum dado para exportar para CSV.")
        return
    all_keys = set().union(*(d.keys() for d in data))
    fieldnames = sorted(list(all_keys))
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"Dados exportados para {filename}")
    except IOError as e:
        print(f"Erro ao escrever arquivo CSV {filename}: {e}")
    except Exception as e:
         print(f"Erro inesperado ao exportar para CSV: {e}")


def scrape_news(site_key, output_format="json", fetch_full_content=False, check_duplicates=True):
    """Função principal para orquestrar o scraping, com opção de checar duplicatas."""
    if site_key not in CONFIG:
        print(f"Erro: Configuração para '{site_key}' não encontrada.")
        return

    config = CONFIG[site_key]
    print(f"Iniciando scraping para: {config['base_url']}")

    processed_hashes = set()
    hashes_filename = config.get("processed_hashes_file")
    if check_duplicates and hashes_filename:
        processed_hashes = load_processed_hashes(hashes_filename)
        print(f"Carregados {len(processed_hashes)} hashes de notícias processadas anteriormente.")

    initial_delay = random.uniform(config["min_delay_seconds"], config["max_delay_seconds"])
    print(f"Aguardando {initial_delay:.2f} segundos antes da primeira requisição...")
    time.sleep(initial_delay)

    html = get_page_content(config["base_url"], config["headers"], config["max_retries"], config["backoff_factor"])

    if html:
        extracted_data = extract_news_data(html, config)
        print(f"Extraídas {len(extracted_data)} notícias da página principal.")

        new_news_items = []
        new_hashes_count = 0
        if check_duplicates and hashes_filename:
            print("Filtrando notícias novas...")
            for news_item in extracted_data:
                news_hash = generate_news_hash(news_item)
                if news_hash and news_hash not in processed_hashes:
                    new_news_items.append(news_item)
                    processed_hashes.add(news_hash)
                    new_hashes_count += 1
                elif news_hash:
                    print(f"  Notícia duplicada encontrada (hash {news_hash[:8]}...), pulando: {news_item.get('title', 'Sem Título')[:50]}...")
                else:
                    print(f"  Aviso: Não foi possível gerar hash para a notícia, incluindo por segurança: {news_item.get('title', 'Sem Título')[:50]}...")
                    new_news_items.append(news_item) # Inclui se não puder gerar hash
            print(f"Encontradas {len(new_news_items)} notícias novas ({new_hashes_count} hashes adicionados). {len(extracted_data) - len(new_news_items)} duplicadas ignoradas.")
        else:
            new_news_items = extracted_data 
          
        if fetch_full_content and config.get("content_selector") and new_news_items:
            print(f"Buscando conteúdo completo das {len(new_news_items)} notícias novas...")
            for i, news_item in enumerate(new_news_items):
                if news_item.get("link"):
                    print(f"  Acessando notícia {i+1}/{len(new_news_items)}: {news_item['link']}")
                    article_delay = random.uniform(config["min_delay_seconds"], config["max_delay_seconds"])
                    time.sleep(article_delay)
                    article_html = get_page_content(news_item["link"], config["headers"], config["max_retries"], config["backoff_factor"])
                    if article_html:
                        try:
                            article_soup = BeautifulSoup(article_html, 'html.parser')
                            content_element = article_soup.select_one(config["content_selector"])
                            if content_element:
                                news_item["full_content"] = content_element.get_text(separator='\n', strip=True)
                                print(f"    Conteúdo completo extraído (primeiros 100 chars): {news_item['full_content'][:100]}...")
                            else:
                                print(f"    Aviso: Seletor de conteúdo '{config['content_selector']}' não encontrado em {news_item['link']}")
                        except Exception as e:
                            print(f"    Erro ao parsear ou extrair conteúdo de {news_item['link']}: {e}")
                    else:
                        print(f"    Falha ao obter conteúdo da página do artigo: {news_item['link']}")
                else:
                     print(f"  Item {i+1} sem link, pulando busca de conteúdo completo.")

        if new_news_items:
            output_filename_base = f"{site_key}_noticias_novas" if check_duplicates else f"{site_key}_noticias"
            if output_format.lower() == "json":
                export_to_json(new_news_items, filename=f"{output_filename_base}.json")
            elif output_format.lower() == "csv":
                export_to_csv(new_news_items, filename=f"{output_filename_base}.csv")
            else:
                print(f"Formato de saída '{output_format}' não suportado. Use 'json' ou 'csv'.")

            if check_duplicates and hashes_filename:
                save_processed_hashes(processed_hashes, hashes_filename)

        else:
            print("Nenhuma notícia nova encontrada ou extraída após processamento.")
            if check_duplicates and hashes_filename and not os.path.exists(hashes_filename):
                 save_processed_hashes(processed_hashes, hashes_filename)

    else:
        print("Não foi possível obter o conteúdo da página principal. Nenhum dado processado ou salvo.")

if __name__ == "__main__":
    target_site = "g1"
    output_type = "json"
    get_full_content = False # Mude para True para buscar o conteúdo completo
    check_for_duplicates = True # Mude para False para não checar duplicatas

    scrape_news(target_site, output_type, fetch_full_content=get_full_content, check_duplicates=check_for_duplicates)

