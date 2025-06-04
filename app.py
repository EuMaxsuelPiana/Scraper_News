from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Sites capixabas
urls = [
    'https://tribunaes.com.br/',
    'https://www.es360.com.br/',
    'https://www.esmais.com.br/',
    'https://www.esfala.com.br/',
    'https://jornaldoes.com.br/'
]

@app.route('/')
def index():
    todas_noticias = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }

    for url in urls:
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            titulos = soup.find_all('h2')  # adapte aqui se o site tiver outra tag
            noticias = [titulo.get_text(strip=True) for titulo in titulos]
            todas_noticias.append({'site': url, 'noticias': noticias})
        except:
            todas_noticias.append({'site': url, 'noticias': ['Erro ao carregar']})
    
    return render_template('index.html', todas_noticias=todas_noticias)
