#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Livrando
Organizador Automático de Livros com Interface Tkinter
-----------------------------------------------------
# === Livrando.py (versão corrigida e comentada) ===
# Este script organiza livros digitais (PDF, EPUB, DOCX...) em pastas com base em metadados.
# Fluxo:
# 1. Percorrer pasta de entrada.
# 2. Para cada arquivo, tentar extrair ISBN.
# 3. Se ISBN encontrado -> buscar metadados em APIs (Google Books, Open Library).
# 4. Caso não tenha ISBN, usar nome do arquivo para pesquisa.
# 5. Normalizar e validar metadados.
# 6. Renomear e mover arquivos para pasta de saída (por autor ou gênero).
# 7. Se configurado, baixar capa e salvar na pasta do livro.

Recursos principais (Nível 3):
- Lê arquivos de uma pasta (EPUB, PDF e outros comuns) e tenta extrair metadados básicos
- Consulta Google Books API e Open Library para completar/corrigir metadados
- Renomeia arquivos seguindo um padrão configurável e organiza em pastas por Autor ou Gênero/Autor
- Faz download da capa (opcional) ao lado do arquivo
- Gera log CSV detalhado e um índice CSV da biblioteca resultante
- Interface simples com Tkinter: seleção de pastas, opções e execução com barra de progresso

Dependências sugeridas:
    pip install requests ebooklib PyPDF2 Pillow

Observações:
- Chave da Google Books API é opcional. Sem chave, ainda funciona (com limites). Caso tenha chave, informe no campo apropriado para melhorar a confiabilidade.
- Metadados de gênero/categoria são mais consistentes na Google Books; a Open Library serve como fallback.
- Para MOBI/AZW3, o script usa heurística (nome do arquivo + APIs), pois ler metadados nativos desses formatos não é trivial sem libs específicas.

Autor: ChatGPT (GPT-5 Thinking)
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import requests
import re
import csv
import sys
import json
import time
import queue
import shutil
import hashlib
import unicodedata
import string
import threading
from PIL import Image
from io import BytesIO
from ebooklib import epub
from PyPDF2 import PdfReader
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List, Tuple
import configparser
import socket
import traceback
from datetime import datetime

# Configuração
CONFIG_FILE = "livrando_config.ini"

# Terceiras
try:
    import requests
except Exception:
    print("[ERRO] A biblioteca 'requests' é necessária. Instale com: pip install requests")
    raise

# EPUB
try:
    from ebooklib import epub  # type: ignore
    HAS_EPUB = True
except Exception:
    HAS_EPUB = False

# PDF
try:
    import PyPDF2  # type: ignore
    HAS_PDF = True
except Exception:
    HAS_PDF = False

# Formatos suportados expandidos
SUPPORTED_EXTS = {'.epub', '.pdf', '.mobi', '.azw3', '.djvu', '.fb2', '.txt', '.doc', '.docx', '.rtf', '.zip', '.rar', '.7z'}

# Configurações padrão
DEFAULT_CONFIG = {
    'Geral': {
        'log_dirname': '1. logs',
        'unknown_dirname': '2. Não Localizados',
        'duplicates_dirname': '3. Duplicados',
        'covers_dirname': 'covers',
        'organize_mode': 'autor',
        'filename_pattern': '{author} - {title} ({year})',
        'language': 'pt'
    },
    'Opcoes': {
        'baixar_capas': 'True',
        'remover_acentos': 'True',
        'limpar_caracteres': 'True',
        'ignorar_sem_metadados': 'False'
    },
    'API': {
        'google_books_key': ''
    },
    'Pastas': {
        'pasta_origem': '',
        'pasta_destino': ''
    }
}

# ------------------------------ Configuração ------------------------------

def load_config():
    """Carrega configuração do arquivo INI ou usa padrão"""
    config = configparser.ConfigParser()
    # Configurar valores padrão
    for section, options in DEFAULT_CONFIG.items():
        if not config.has_section(section):
            config.add_section(section)
        for key, value in options.items():
            config.set(section, key, value)
    
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')
    
    return config

def save_config(config):
    """Salva configuração no arquivo INI"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
        config.write(configfile)

def delete_config():
    """Exclui arquivo de configuração"""
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)

def get_config_value(config, section, key, default=None):
    """Obtém valor da configuração com fallback"""
    try:
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return default

# ------------------------------ Teste de Conexão ------------------------------

def test_internet_connection():
    """Testa se há conexão com a internet"""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

def test_google_books_api(api_key=None):
    """Testa a conexão com Google Books API"""
    try:
        url = "https://www.googleapis.com/books/v1/volumes"
        params = {"q": "python", "maxResults": 1}
        if api_key:
            params["key"] = api_key
        response = requests.get(url, params=params, timeout=10)
        return response.status_code == 200, f"Google Books: {'Com chave' if api_key else 'Sem chave'} - Status: {response.status_code}"
    except Exception as e:
        return False, f"Google Books: Erro - {str(e)}"

def test_open_library():
    """Testa a conexão com Open Library"""
    try:
        url = "https://openlibrary.org/search.json"
        params = {"q": "python", "limit": 1}
        response = requests.get(url, params=params, timeout=10)
        return response.status_code == 200, f"Open Library: Status: {response.status_code}"
    except Exception as e:
        return False, f"Open Library: Erro - {str(e)}"

# ------------------------------ Utilidades ------------------------------

def clean_search_query(text):
    """Limpa completamente a query de busca"""
    if not text:
        return ""
    
    # Remover completamente lixo digital
    junk_patterns = [
        r'\(z-library\)', r'\(z-lib\)', r'\(libgen\)', r'\(pdf\)', r'\(epub\)', 
        r'\bmicrosoft\s+word\b',  # Remove "Microsoft Word" como frase
        r'\[.*?\]', r'\(.*?\)', r'\d+p', r'\.(pdf|epub|mobi|azw3|docx?|txt|zip|rar)$',
        r'www\.\w+\.com', r'\.com', r'\.org', r'\.net', r'http[s]?://',
        r'\[1\]', r'\.\.\.', r'\b\w*libgen\w*\b', r'\b\w*zlib\w*\b',
        r'\b\w*download\w*\b', r'\b\w*free\w*\b', r'\b\w*ebook\w*\b'
    ]
    
    for pattern in junk_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Substituir caracteres especiais por espaços
    #text = re.sub(r'[_-]', ' ', text)
    
    # Remover números isolados e caracteres especiais
    text = re.sub(r'\b\d+\b', ' ', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Manter acentos e caracteres especiais (importantes para nomes)
    text = re.sub(r'[^\w\sáéíóúàèìòùâêîôûãõäëïöüçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÄËÏÖÜÇ]', '', text)
    
    # Normalizar espaços
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
    

def construct_search_query(local_meta, filename):
    """Constrói query de busca inteligente"""
    query_bits = []
    
    # Primeiro tentar metadados locais
    if local_meta and local_meta.get('title'):
        title = clean_search_query(local_meta['title'])
        if len(title) > 2:
            query_bits.append(title)
    
    # Fallback para nome do arquivo
    if not query_bits:
        name = os.path.splitext(filename)[0]
        name_clean = clean_search_query(name)
        if len(name_clean) > 2:
            query_bits.append(name_clean)
    
    return ' '.join(query_bits) if query_bits else ""

def test_api_connection():
    """Testa se as APIs estão respondendo"""
    try:
        # Testar Google Books
        google_url = "https://www.googleapis.com/books/v1/volumes?q=python&maxResults=1"
        google_response = requests.get(google_url, timeout=10)
        google_ok = google_response.status_code == 200
        
        # Testar Open Library
        ol_url = "https://openlibrary.org/search.json?q=python&limit=1"
        ol_response = requests.get(ol_url, timeout=10)
        ol_ok = ol_response.status_code == 200
        
        return google_ok, ol_ok
    except:
        return False, False

def remover_acentos(texto):
    """Remove acentos do texto mantendo caracteres especiais"""
    if not texto:
        return ""
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto

def limpar_caracteres_especiais(texto):
    """Remove caracteres especiais mantendo letras, números e espaços"""
    if not texto:
        return ""
    texto = re.sub(r'[^\w\s\-\(\)\.]', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def calcular_hash(caminho):
    """Calcula hash MD5 do arquivo"""
    md5 = hashlib.md5()
    try:
        with open(caminho, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)
        return md5.hexdigest()
    except:
        return None

def normalizar_texto(texto, remover_acentos_flag=True, limpar_caracteres_flag=True):
    """Normaliza texto com opções de limpeza"""
    if not texto:
        return ""
    
    if remover_acentos_flag:
        texto = remover_acentos(texto)
    
    if limpar_caracteres_flag:
        texto = limpar_caracteres_especiais(texto)
    
    return texto.strip()

def gerar_hash_md5(filepath):
    """Gera hash MD5 do arquivo"""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None

def truncar_nome(nome, limite=200):
    """Trunca nome se muito longo"""
    return nome[:limite] if len(nome) > limite else nome

def normalize_spaces(s: str) -> str:
    """Normaliza espaços em branco"""
    return re.sub(r"\s+", " ", s).strip()

def sanitize_filename(name: str, max_len: int = 180) -> str:
    """Remove caracteres inválidos para nome de arquivo e limita tamanho."""
    name = normalize_spaces(name)
    invalid = '<>:"/\\|?*\n\r\t'
    table = str.maketrans({c: '-' for c in invalid})
    name = name.translate(table)
    name = ''.join(ch for ch in name if ch.isprintable() or ch in 'áéíóúàèìòùâêîôûãõäëïöüçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛãõÄËÏÖÜÇ')
    name = re.sub(r"[-_]{2,}", "-", name)
    return name[:max_len].rstrip('. ')

def year_from_date_str(date_str: Optional[str]) -> Optional[str]:
    """Extrai ano de string de data"""
    if not date_str:
        return None
    m = re.match(r"(\d{4})", date_str)
    return m.group(1) if m else None

def token_score(a: str, b: str) -> float:
    """Pontuação simples de similaridade por interseção de tokens (0..1)."""
    if not a or not b:
        return 0.0
    at = set(re.findall(r"\w+", a.lower()))
    bt = set(re.findall(r"\w+", b.lower()))
    if not at or not bt:
        return 0.0
    inter = len(at & bt)
    uni = len(at | bt)
    return inter / max(1, uni)

def extract_metadata_from_filename(filename):
    """Extrai metadados do nome do arquivo de forma inteligente"""
    name, ext = os.path.splitext(filename)
    
    # Primeiro, limpar lixo digital
    name = clean_search_query(name)
    
    # Padrões comuns de nomes de livros
    patterns = [
        # Padrão: Autor - Título
        r'^(.*?)[\s\-–—]+([^\-–—]+)$',
        # Padrão: Título - Autor  
        r'^([^\-–—]+)[\s\-–—]+(.*?)$',
        # Padrão: Título por Autor
        r'^(.+?)\s+por\s+(.+?)$',
        # Padrão: Título (Autor)
        r'^(.+?)\s*[\(\[](.+?)[\)\]]$',
        # Autor - Título (Ano)
        r'^(.*?)[\s\-–—]+(.+?)(?:\s*\((\d{4})\))?$',
        # Título - Autor (Ano)
        r'^(.+?)[\s\-–—]+(.*?)(?:\s*\((\d{4})\))?$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            part1, part2 = match.groups()
            part1 = part1.strip()
            part2 = part2.strip()
            
            # Heurística para determinar qual é autor e qual é título
            if looks_like_author(part1) and looks_like_title(part2):
                return {'title': part2, 'authors': [part1]}
            elif looks_like_title(part1) and looks_like_author(part2):
                return {'title': part1, 'authors': [part2]}
            elif looks_like_title(part1) and looks_like_title(part2):
                # Ambos parecem títulos, usar o mais longo como título
                if len(part1) > len(part2):
                    return {'title': part1, 'authors': None}
                else:
                    return {'title': part2, 'authors': None}
    
    # Fallback: se não conseguiu separar, usar tudo como título
    return {'title': name, 'authors': None}

def looks_like_author(text):
    """Verifica se o texto parece ser um nome de autor"""
    if not text or len(text) < 3:
        return False
    
    # Autores geralmente têm 2-3 palavras
    words = text.split()
    if len(words) > 4:
        return False
    
    # Verificar padrões de nome
    if (re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', text) or  # Nome Sobrenome
        re.match(r'^[A-Z][a-z]+, [A-Z][a-z]+', text)):  # Sobrenome, Nome
        return True
    
    # Nomes comuns de autores conhecidos
    known_authors = ['stephen king', 'agatha christie', 'j.k. rowling', 'paulo coelho', 
                    'dan brown', 'george r.r. martin', 'j.r.r. tolkien', 'rick riordan']
    
    if text.lower() in known_authors:
        return True
    
    return False

def extract_title_author_from_filename(filename):
    """Extrai título e autor do nome do arquivo considerando padrões comuns"""
    
    # Padrões comuns de nomes de arquivos de livros
    patterns = [
        # Padrão: Título - Autor (Ano)
        r'^(.*?)\s*[-–—]\s*(.*?)\s*[\(\[]\d{4}[\)\]]',
        # Padrão: Autor - Título (Ano)
        r'^(.*?)\s*[-–—]\s*(.*?)\s*[\(\[]\d{4}[\)\]]',
        # Padrão: Título - Autor
        r'^(.*?)\s*[-–—]\s*(.*?)$',
        # Padrão: Autor - Título  
        r'^(.*?)\s*[-–—]\s*(.*?)$',
        # Padrão: Título por Autor
        r'^(.*?)\s+por\s+(.*?)$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, filename, re.IGNORECASE)
        if match:
            part1, part2 = match.groups()
            part1 = part1.strip()
            part2 = part2.strip()
            
            # Determinar qual parte é título e qual é autor
            if looks_like_author(part1) and looks_like_title(part2):
                return part2, part1  # Título, Autor
            elif looks_like_title(part1) and looks_like_author(part2):
                return part1, part2  # Título, Autor
            elif looks_like_title(part1) and looks_like_title(part2):
                return part1, None  # Assumir que a primeira parte é título
            else:
                return part2, part1  # Tentativa genérica
    
    # Se não encontrou padrão, retornar o nome completo como título
    return filename, None
    
def clean_search_query_metadados(text):
    """Limpeza para metadados - remove apenas lixo digital"""
    if not text:
        return ""
    
    # Remover apenas lixo digital óbvio
    junk_patterns = [
        r'\(z-library\)', r'\(z-lib\)', r'\(libgen\)', 
        r'www\.\w+\.\w+', r'http[s]?://\S+',
        r'\[.*?\]', r'\(.*?\)'
    ]
    
    for pattern in junk_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Manter a estrutura original do texto
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def clean_search_query_nome_arquivo(text):
    """Limpeza para nome do arquivo - remove lixo mas mantém separadores"""
    if not text:
        return ""
    
    # Remover lixo digital
    junk_patterns = [
        r'\(z-library\)', r'\(z-lib\)', r'\(libgen\)', 
        r'www\.\w+\.\w+', r'http[s]?://\S+',
        r'\[.*?\]', r'\(.*?\)', r'\.\.\.',
        r'\b\d+p\b', r'\b\d+k\b', r'\[\d+\]',
        r'reidoebook', r'livrosparatodos', r'z-lib',
        r'\.com', r'\.net', r'\.org'
    ]
    
    for pattern in junk_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Substituir underlines por espaços, mas manter hífens (podem ser separadores)
    text = re.sub(r'_', ' ', text)
    
    # Remover extensões de arquivo
    text = re.sub(r'\.(pdf|epub|mobi|azw3|docx?|txt|zip|rar)$', '', text, flags=re.IGNORECASE)
    
    # Normalizar espaços
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def looks_like_title(text):
    """Verifica se o texto parece ser um título"""
    if not text or len(text) < 3:
        return False
    
    # Títulos geralmente são mais longos que autores
    if len(text) < 5:
        return False
    
    # Títulos não devem ser apenas iniciais
    if re.match(r'^[A-Z\.\s]+$', text):
        return False
    
    return True
    
def extract_isbn(filepath):
    """Tenta extrair ISBN de arquivos com tratamento de erro robusto"""
    try:
        if filepath.lower().endswith('.pdf'):
            return extract_isbn_from_pdf(filepath)
        elif filepath.lower().endswith('.epub'):
            return extract_isbn_from_epub(filepath)
    except Exception as e:
        print(f"Erro ao extrair ISBN de {filepath}: {e}")
    
    return None

def extract_isbn_rigorous(filepath):
    """Extrai ISBN com foco em áreas específicas do PDF onde ISBNs reais aparecem"""
    try:
        # Para PDFs, focar em áreas onde ISBNs geralmente aparecem
        if filepath.lower().endswith('.pdf'):
            return extract_isbn_from_pdf_smart(filepath)
        elif filepath.lower().endswith('.epub'):
            return extract_isbn_from_epub_smart(filepath)
        else:
            # Para outros formatos, tentar extração genérica
            return extract_isbn_generic(filepath)
    except Exception as e:
        print(f"Erro ao extrair ISBN de {filepath}: {e}")
        return None

def extract_isbn_from_pdf_smart(filepath):
    """Extrai ISBN de PDFs de forma inteligente, focando em áreas relevantes"""
    try:
        with open(filepath, 'rb') as f:
            # Ler apenas as primeiras páginas onde ISBNs geralmente aparecem
            reader = PdfReader(f)
            text_chunks = []
            
            # Coletar texto das primeiras 5 páginas e últimas 2 páginas
            for i, page in enumerate(reader.pages):
                if i < 5 or i > len(reader.pages) - 3:  # Primeiras 5 e últimas 2
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_chunks.append(page_text)
                    except:
                        continue
            
            text = " ".join(text_chunks)
            
            # Procurar ISBNs em contextos específicos
            isbn_patterns = [
                r'ISBN[-]*(1[03])?[:]?[\s]*([0-9X\-]{10,17})',
                r'ISBN[\s]*([0-9X\-]{10,17})',
                r'(97[89][\-]?[0-9]{1,5}[\-]?[0-9]{1,7}[\-]?[0-9]{1,6}[\-]?[0-9X])',
            ]
            
            found_isbns = []
            
            for pattern in isbn_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    isbn_candidate = re.sub(r'[^\dX]', '', match.group().upper())
                    
                    # Validação rigorosa mas realista
                    if (len(isbn_candidate) in [10, 13] and 
                        is_valid_isbn(isbn_candidate) and
                        not isbn_candidate.startswith(('0000', '1111', '1234', '9999')) and
                        len(set(isbn_candidate)) > 4):  # Não pode ter muitos dígitos repetidos
                        
                        # Verificar contexto - ISBN deve estar perto de palavras relevantes
                        context = text[max(0, match.start()-50):match.end()+50].lower()
                        if any(keyword in context for keyword in ['isbn', 'book', 'edition', 'publish']):
                            found_isbns.append(isbn_candidate)
            
            if found_isbns:
                return found_isbns[0]  # Retornar o primeiro ISBN válido
                
    except Exception as e:
        print(f"Erro ao extrair ISBN de PDF {filepath}: {e}")
    
    return None

def extract_isbn_generic(filepath):
    """Extração genérica de ISBN para outros formatos"""
    try:
        with open(filepath, 'rb') as f:
            content = f.read(50000)  # 50KB
            text = content.decode('utf-8', errors='ignore')
            
            isbn_patterns = [
                r'ISBN[-]*(1[03])?[:]?[\s]*([0-9X\-]{10,17})',
                r'ISBN[\s]*([0-9X\-]{10,17})',
            ]
            
            for pattern in isbn_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[1] if len(match) > 1 else match[0]
                    
                    isbn_candidate = re.sub(r'[^\dX]', '', match.upper())
                    
                    if (len(isbn_candidate) in [10, 13] and 
                        is_valid_isbn(isbn_candidate) and
                        not isbn_candidate.startswith(('0000', '1111', '1234'))):
                        return isbn_candidate
                        
    except Exception:
        pass
    
    return None

def extract_isbn_from_pdf(filepath):
    """Extrai ISBN de PDFs com validação rigorosa"""
    try:
        with open(filepath, 'rb') as f:
            # Ler apenas parte inicial do arquivo
            content = f.read(100000)  # 100KB
            text = content.decode('utf-8', errors='ignore')
            
            # Padrões de ISBN mais específicos
            isbn_patterns = [
                r'ISBN[-]*(1[03])?[:]?[\s]*([0-9X\-]{10,17})',
                r'ISBN[\s]*([0-9X\-]{10,17})',
                r'(97[89][\-]?[0-9]{1,5}[\-]?[0-9]{1,7}[\-]?[0-9]{1,6}[\-]?[0-9X])',
                r'([0-9]{1,5}[\-]?[0-9]{1,7}[\-]?[0-9]{1,6}[\-]?[0-9X])'
            ]
            
            for pattern in isbn_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[1] if len(match) > 1 else match[0]
                    
                    # Limpar e validar ISBN
                    isbn_candidate = re.sub(r'[^\dX]', '', match)
                    
                    # Validar comprimento e checksum
                    if len(isbn_candidate) in [10, 13] and is_valid_isbn(isbn_candidate):
                        return isbn_candidate
                        
    except Exception as e:
        print(f"Erro no extract_isbn_from_pdf para {filepath}: {e}")
    
    return None

def is_valid_isbn(isbn):
    """Validação RIGOROSA de ISBN"""
    isbn = re.sub(r'[^\dX]', '', str(isbn)).upper()
    
    # Rejeitar ISBNs falsos óbvios
    if (isbn.startswith('0000000') or 
        isbn == '0000000000' or 
        isbn == '0000000000000' or
        len(set(isbn)) == 1):  # Todos dígitos iguais
        return False
    
    if len(isbn) == 10:
        # Validar ISBN-10
        total = 0
        for i in range(9):
            if not isbn[i].isdigit():
                return False
            total += int(isbn[i]) * (10 - i)
        
        if isbn[9] == 'X':
            check = 10
        elif isbn[9].isdigit():
            check = int(isbn[9])
        else:
            return False
            
        return (total + check) % 11 == 0
        
    elif len(isbn) == 13:
        # Validar ISBN-13
        if not isbn.startswith('978') and not isbn.startswith('979'):
            return False
            
        total = 0
        for i in range(12):
            if not isbn[i].isdigit():
                return False
            total += int(isbn[i]) * (1 if i % 2 == 0 else 3)
            
        check = 10 - (total % 10)
        if check == 10:
            check = 0
            
        return isbn[12] == str(check)
        
    return False

def is_metadata_consistent(local_meta, api_meta):
    """Verifica se os metadados locais são consistentes com os da API"""
    if not local_meta or not api_meta:
        return False
    
    local_title = local_meta.get('title', '').lower()
    api_title = api_meta.get('title', '').lower()
    
    # Se os títulos são muito diferentes, rejeitar
    if local_title and api_title:
        similarity = token_score(local_title, api_title)
        if similarity < 0.3:  # Muito diferentes
            return False
    
    return True

def is_high_quality_local_metadata(meta):
    """Avalia se os metadados locais são de alta qualidade"""
    if not meta:
        return False
    
    title = meta.get('title', '')
    authors = meta.get('authors', [])
    
    # Validar título
    if (not title or 
        len(title) < 3 or 
        title.isdigit() or
        any(junk in title.lower() for junk in ['unknown', 'untitled', 'document'])):
        return False
    
    # Validar autores
    if not authors or any(not auth or len(auth) < 3 for auth in authors):
        return False
    
    # Validar que não é lixo comum
    author_str = ' '.join(authors).lower()
    if any(junk in author_str for junk in ['unknown', 'anonymous', 'user', 'admin']):
        return False
    
    return True
    
def is_high_quality_filename_metadata(meta, filename):
    """Avalia se os metadados extraídos do filename são de alta qualidade"""
    if not meta:
        return False
    
    title = meta.get('title', '')
    authors = meta.get('authors', [])
    
    # Validar título
    if (not title or 
        len(title) < 5 or  # Títulos muito curtos são suspeitos
        title.isdigit() or
        len(title) > 100):  # Títulos muito longos
        return False
    
    # Validar autores
    if not authors or any(not auth or len(auth) < 3 for auth in authors):
        return False
    
    # Validar consistência com o filename
    filename_lower = filename.lower()
    title_lower = title.lower()
    
    # O título deve estar contido no filename
    if title_lower not in filename_lower:
        return False
    
    return True

def extract_isbn_from_epub(filepath):
    """Extrai ISBN de EPUBs"""
    try:
        book = epub.read_epub(filepath)
        identifiers = book.get_metadata('DC', 'identifier')
        if identifiers:
            for identifier in identifiers:
                if identifier[0]:
                    id_str = str(identifier[0])
                    if 'isbn' in id_str.lower():
                        isbn = re.sub(r'[^\dX]', '', id_str)
                        if len(isbn) in [10, 13]:
                            return isbn
                    # Verificar se é um ISBN válido
                    isbn_candidate = re.sub(r'[^\dX]', '', id_str)
                    if len(isbn_candidate) in [10, 13]:
                        return isbn_candidate
    except:
        pass
    
    return None

def search_by_isbn(isbn, api_key=None):
    """Busca livro por ISBN com validação EXTREMAMENTE rigorosa"""
    try:
        # Primeiro tenta Google Books
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        if api_key:
            url += f"&key={api_key}"
        
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "items" in data and len(data["items"]) > 0:
                for item in data["items"]:
                    volume_info = item.get("volumeInfo", {})
                    industry_ids = volume_info.get("industryIdentifiers", [])
                    
                    # VERIFICAÇÃO RIGOROSA: deve ter correspondência exata de ISBN
                    exact_match = False
                    for id_obj in industry_ids:
                        id_type = id_obj.get("type", "").upper()
                        id_value = id_obj.get("identifier", "").replace("-", "")
                        current_isbn = isbn.replace("-", "")
                        
                        if (id_value == current_isbn and 
                            id_type in ["ISBN_10", "ISBN_13"]):
                            exact_match = True
                            break
                    
                    if exact_match:
                        # VALIDAÇÃO ADICIONAL: deve ter título e autor válidos
                        title = volume_info.get("title", "")
                        authors = volume_info.get("authors", [])
                        
                        if (title and len(title) > 2 and 
                            authors and len(authors) > 0 and 
                            len(authors[0]) > 2):
                            
                            # Extrair ano corretamente
                            published_date = volume_info.get("publishedDate", "")
                            year = None
                            if published_date:
                                year_match = re.search(r'(\d{4})', published_date)
                                if year_match:
                                    year = year_match.group(1)
                            
                            return {
                                "title": title,
                                "authors": authors,
                                "publishedDate": year,
                                "categories": volume_info.get("categories", []),
                                "imageLinks": volume_info.get("imageLinks", {}),
                                "fonte": "Google Books (ISBN)",
                                "score": 1.0
                            }
        
        # Open Library apenas se não encontrou no Google Books
        url = f"https://openlibrary.org/isbn/{isbn}.json"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            
            # Verificar correspondência exata
            isbn_10 = data.get("isbn_10", [])
            isbn_13 = data.get("isbn_13", [])
            
            if isbn in isbn_10 or isbn in isbn_13:
                authors = []
                for auth in data.get("authors", []):
                    if isinstance(auth, dict) and auth.get("key"):
                        # Buscar detalhes do autor
                        try:
                            auth_url = f"https://openlibrary.org{auth['key']}.json"
                            auth_response = requests.get(auth_url, timeout=10)
                            if auth_response.status_code == 200:
                                auth_data = auth_response.json()
                                authors.append(auth_data.get("name", ""))
                        except:
                            continue
                
                if not authors:
                    authors = [auth.get("name", "") for auth in data.get("authors", []) if auth.get("name")]
                
                # Validar qualidade
                if (data.get("title") and authors and 
                    len(data["title"]) > 2 and len(authors[0]) > 2):
                    
                    return {
                        "title": data.get("title"),
                        "authors": authors,
                        "publishedDate": str(data.get("publish_date")) if data.get("publish_date") else None,
                        "categories": data.get("subjects", [])[:3],
                        "fonte": "Open Library (ISBN)",
                        "score": 1.0
                    }
                    
    except Exception as e:
        print(f"Erro na busca por ISBN {isbn}: {e}")
    
    return None


def extract_year_from_date(date_str):
    """Extrai ano de forma robusta de strings de data"""
    if not date_str:
        return None
    
    # Padrões comuns de data
    patterns = [
        r'(\d{4})',  # Apenas ano (1999)
        r'(\d{4})-\d{2}-\d{2}',  # ISO (1999-12-31)
        r'\d{2}/(\d{4})',  # MM/YYYY
        r'\d{2}-\d{2}-(\d{4})',  # DD-MM-YYYY
    ]
    
    for pattern in patterns:
        match = re.search(pattern, str(date_str))
        if match:
            year = match.group(1)
            # Validar se é um ano plausível (entre 1000 e ano atual + 1)
            current_year = datetime.now().year
            if 1000 <= int(year) <= current_year + 1:
                return year
    
    return None
    
def extract_office_metadata(filepath):
    """Tenta extrair metadados de arquivos Office de forma segura"""
    try:
        if filepath.lower().endswith(('.doc', '.docx', '.rtf')):
            # Para arquivos Office, ler as primeiras linhas para tentar encontrar título/autor
            with open(filepath, 'rb') as f:
                # Ler apenas os primeiros bytes para evitar arquivos muito grandes
                content = f.read(5000)
                text = content.decode('utf-8', errors='ignore')
                
                # Padrões comuns em arquivos Office
                patterns = [
                    r'Title:\s*(.*?)\n',
                    r'Author:\s*(.*?)\n',
                    r'<title>(.*?)</title>',
                    r'<author>(.*?)</author>',
                ]
                
                metadata = {}
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        if 'title' in pattern.lower() and not metadata.get('title'):
                            metadata['title'] = match.group(1).strip()
                        elif 'author' in pattern.lower() and not metadata.get('author'):
                            metadata['author'] = match.group(1).strip()
                
                return metadata
    except:
        pass
    return {}

def normalize_unknown_filename(filename):
    """Normaliza nome de arquivo para arquivos não identificados - SEM padrão de nome"""
    name, ext = os.path.splitext(filename)
    
    # Remover padrões comuns de lixo mas manter informações úteis
    patterns_to_remove = [
        r'reidoebook\[?\d*\]?\.com[+-]*',
        r'www\.\w+\.com',
        r'z-library',
        r'\(z-library\)',
        r'pdfcoffee\.com',
        r'\(.*?\)',
        r'\[.*?\]',
        r'\d{4}',
    ]
    
    for pattern in patterns_to_remove:
        name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)
    
    # Substituir caracteres especiais por espaços
    name = re.sub(r'[+_]', ' ', name)
    
    # Remover múltiplos espaços e caracteres especiais problemáticos
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[^\w\s\-\.]', '', name)
    name = name.strip()
    
    # Se ficou muito curto, usar nome original (mais limpo)
    if len(name) < 3:
        name = re.sub(r'[^\w\s\-\.]', '', os.path.splitext(filename)[0])
        name = re.sub(r'[+_]', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
    
    # Não usar "Autor Desconhecido" no nome do arquivo
    # Apenas retornar o nome normalizado
    return name + ext


# --- Funções utilitárias ---

def extrair_metadados_ebook(filepath):
    """Extrai metadados de arquivos EPUB e PDF"""
    meta = {"titulo": None, "autor": None, "ano": None, "genero": None}
    try:
        if filepath.lower().endswith(".epub"):
            book = epub.read_epub(filepath)
            meta["titulo"] = book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else None
            meta["autor"] = book.get_metadata('DC', 'creator')[0][0] if book.get_metadata('DC', 'creator') else None
            meta["ano"] = book.get_metadata('DC', 'date')[0][0][:4] if book.get_metadata('DC', 'date') else None
        elif filepath.lower().endswith(".pdf"):
            with open(filepath, 'rb') as f:
                pdf = PdfReader(f)
                if hasattr(pdf, 'metadata') and pdf.metadata:
                    info = pdf.metadata
                    meta["titulo"] = info.title if info.title else None
                    meta["autor"] = info.author if info.author else None
        return meta
    except Exception as e:
        print(f"Erro ao extrair metadados de {filepath}: {e}")
        return meta
        
        
        
        # ESTOU REMOVENDO def construct_search_query DAQUI


def validate_metadata(meta, fonte):
    """Validação CORRETA - verifica se os dados são plausíveis"""
    if not meta or not isinstance(meta, dict):
        return False
    
    # Verificar título
    title = meta.get('title')
    if not title or not isinstance(title, str) or len(title.strip()) < 2:
        return False
    
    # Verificar autores
    authors = meta.get('authors', [])
    if not authors or not isinstance(authors, list) or len(authors) == 0:
        return False
    
    author = authors[0]
    if not author or not isinstance(author, str) or len(author.strip()) < 2:
        return False
    
    # Verificar se não é lixo comum
    title_lower = title.lower()
    author_lower = author.lower()
    
    invalid_titles = ['unknown', 'untitled', 'document', 'file', 'microsoft', 'word']
    invalid_authors = ['unknown', 'anonymous', 'author', 'user', 'admin', 'system', 't_ms02']
    
    if any(invalid in title_lower for invalid in invalid_titles):
        return False
    
    if any(invalid in author_lower for invalid in invalid_authors):
        return False
    
    return True

def apply_text_normalization(meta, remover_acentos_flag, limpar_caracteres_flag):
    """Aplica normalização de texto aos metadados"""
    result = meta.copy()
    
    if result.get('title'):
        title = result['title']
        if remover_acentos_flag:
            title = remover_acentos(title)
        if limpar_caracteres_flag:
            title = limpar_caracteres_especiais(title)
        # Manter capitalização inteligente
        if title.isupper() or title.islower():
            title = title.title()
        result['title'] = title
    
    if result.get('authors'):
        authors = []
        for author in result['authors']:
            if remover_acentos_flag:
                author = remover_acentos(author)
            if limpar_caracteres_flag:
                author = limpar_caracteres_especiais(author)
            if author and author != "Autor Desconhecido":
                authors.append(author)
        result['authors'] = authors if authors else ["Autor Desconhecido"]
    
    return result

def buscar_google_books(titulo, autor, api_key=None):
    """Consulta Google Books API usando título e autor de forma inteligente"""
    try:
        # Se temos tanto título quanto autor, fazer busca específica
        if titulo and autor and autor != "Autor Desconhecido":
            # Tentar busca exata primeiro
            query = f'intitle:"{titulo}" inauthor:"{autor}"'
        elif titulo:
            query = f'intitle:"{titulo}"'
        elif autor and autor != "Autor Desconhecido":
            query = f'inauthor:"{autor}"'
        else:
            return None
        
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=5"
        if api_key:
            url += f"&key={api_key}"
        
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "items" in data and len(data["items"]) > 0:
                best_item = None
                best_score = 0
                
                for item in data["items"]:
                    volume_info = item.get("volumeInfo", {})
                    item_title = volume_info.get("title", "").lower()
                    item_authors = volume_info.get("authors", [])
                    
                    score = 0
                    if titulo and item_title:
                        title_similarity = token_score(titulo.lower(), item_title)
                        score += title_similarity * 0.7
                    
                    if autor and item_authors:
                        author_similarity = max([token_score(autor.lower(), auth.lower()) for auth in item_authors] or [0])
                        score += author_similarity * 0.3
                    
                    if score > best_score:
                        best_score = score
                        best_item = item
                
                if best_item and best_score > 0.3:
                    volume = best_item["volumeInfo"]
                    
                    # Extrair ano corretamente
                    published_date = volume.get("publishedDate", "")
                    year = None
                    if published_date:
                        year_match = re.search(r'(\d{4})', published_date)
                        if year_match:
                            year = year_match.group(1)
                    
                    return {
                        "title": volume.get("title"),
                        "authors": volume.get("authors", []),
                        "publishedDate": year,
                        "categories": volume.get("categories", []),
                        "imageLinks": volume.get("imageLinks", {}),
                        "fonte": "Google Books",
                        "score": best_score
                    }
        return None
    except Exception as e:
        print(f"Erro Google Books API: {e}")
        return None

def buscar_com_query_generica(query, api_key=None):
    """Busca genérica que tenta extrair título e autor da query"""
    # Tentar extrair título e autor da query
    parts = query.split()
    
    # Heurística simples: últimas 2-3 palavras podem ser autor
    if len(parts) >= 4:
        # Tentar padrão: "Título Autor"
        for i in range(2, min(5, len(parts))):
            possible_title = ' '.join(parts[:-i])
            possible_author = ' '.join(parts[-i:])
            
            if (looks_like_title(possible_title) and 
                looks_like_author(possible_author)):
                return buscar_google_books(possible_title, possible_author, api_key)
    
    # Se não conseguiu separar, buscar como título geral
    return buscar_google_books(query, None, api_key)

def buscar_open_library(titulo, autor):
    """Consulta Open Library com mapeamento correto"""
    try:
        if not titulo and not autor:
            return None
            
        query = titulo or ""
        if autor and autor != "Autor Desconhecido":
            query += f" {autor}"
            
        url = f"https://openlibrary.org/search.json?q={query}&limit=5"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "docs" in data and len(data["docs"]) > 0:
                # Encontrar o melhor match
                best_doc = None
                best_score = 0
                
                for doc in data["docs"]:
                    doc_title = doc.get("title", "").lower()
                    doc_authors = doc.get("author_name", [])
                    
                    score = 0
                    if titulo and doc_title:
                        title_similarity = token_score(titulo.lower(), doc_title)
                        score += title_similarity * 0.7
                    
                    if autor and doc_authors:
                        author_similarity = max([token_score(autor.lower(), auth.lower()) for auth in doc_authors] or [0])
                        score += author_similarity * 0.3
                    
                    if score > best_score:
                        best_score = score
                        best_doc = doc
                
                if best_doc and best_score > 0.3:
                    return {
                        "title": best_doc.get("title"),
                        "authors": best_doc.get("author_name", []),
                        "publishedDate": str(best_doc.get("first_publish_year")) if best_doc.get("first_publish_year") else None,
                        "categories": best_doc.get("subject", [])[:3] if best_doc.get("subject") else [],
                        "imageLinks": {
                            "thumbnail": f"https://covers.openlibrary.org/b/id/{best_doc.get('cover_i')}-M.jpg" if best_doc.get('cover_i') else None
                        },
                        "fonte": "Open Library",
                        "score": best_score
                    }
        return None
    except Exception as e:
        print(f"Erro Open Library: {e}")
        return None

def baixar_capa(url, caminho, fonte):
    """Baixa capa do livro"""
    try:
        response = requests.get(url, stream=True, timeout=15)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            if image.mode in ('RGBA', 'LA'):
                image = image.convert('RGB')
            image.save(caminho, 'JPEG', quality=85)
            return True, fonte
    except Exception as e:
        print(f"Erro ao baixar capa: {e}")
    return False, None

# ------------------------------ Metadados locais ------------------------------

def extract_local_metadata(path, ext):
    """Extrai metadados locais baseado na extensão do arquivo"""
    metadata = {}
    
    try:
        if ext == '.epub':
            metadata = read_epub_metadata(path)
        elif ext == '.pdf':
            metadata = read_pdf_metadata(path)
        elif ext in ['.doc', '.docx', '.rtf']:
            metadata = extract_office_metadata(path)
    except Exception as e:
        print(f"Erro ao extrair metadados locais de {path}: {e}")
    
    return metadata

def read_epub_metadata(path: str) -> Dict[str, Any]:
    """Lê metadados de arquivos EPUB"""
    data: Dict[str, Any] = {}
    if not HAS_EPUB:
        return data
    try:
        book = epub.read_epub(path)
        titles = book.get_metadata('DC', 'title')
        if titles:
            data['title'] = normalize_spaces(' '.join([t[0] for t in titles if t and t[0]]))
        authors = book.get_metadata('DC', 'creator')
        if authors:
            auths = [a[0] for a in authors if a and a[0]]
            data['authors'] = [normalize_spaces(a) for a in auths]
        dates = book.get_metadata('DC', 'date')
        if dates and dates[0] and dates[0][0]:
            data['publishedDate'] = year_from_date_str(str(dates[0][0]))
        subjects = book.get_metadata('DC', 'subject')
        if subjects:
            data['categories'] = [normalize_spaces(s[0]) for s in subjects if s and s[0]]
    except Exception as e:
        print(f"Erro ao ler EPUB {path}: {e}")
    return data

def read_pdf_metadata(path: str) -> Dict[str, Any]:
    """Lê metadados de arquivos PDF com tratamento de erro robusto"""
    data: Dict[str, Any] = {}
    if not HAS_PDF:
        return data
    
    try:
        with open(path, 'rb') as f:
            # Verificar se o arquivo é um PDF válido antes de tentar ler
            try:
                reader = PyPDF2.PdfReader(f)
                
                # Verificar se o PDF está criptografado ou corrompido
                if (hasattr(reader, 'metadata') and reader.metadata):
                    info = reader.metadata
                    if info:
                        if info.title and str(info.title).strip():
                            data['title'] = normalize_spaces(str(info.title))
                        if info.author and str(info.author).strip():
                            data['authors'] = [normalize_spaces(str(info.author))]
            except Exception as inner_error:
                # Se falhar, tentar método alternativo
                print(f"Erro ao ler PDF {path} (tentando fallback): {inner_error}")
                return try_pdf_fallback(path)
                
    except Exception as e:
        print(f"Erro ao abrir PDF {path}: {e}")
    
    return data

def try_pdf_fallback(path):
    """Tenta método alternativo para PDFs problemáticos"""
    data = {}
    try:
        # Tentar extrair texto das primeiras páginas para encontrar título
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            if len(reader.pages) > 0:
                # Ler apenas primeira página para evitar problemas
                try:
                    page_text = reader.pages[0].extract_text()
                    if page_text:
                        # Procurar padrões de título
                        lines = page_text.split('\n')
                        for line in lines[:5]:  # Primeiras 5 linhas
                            line = line.strip()
                            if (len(line) > 10 and len(line) < 100 and 
                                not line.isdigit() and 
                                not re.match(r'^\d+$', line) and
                                not re.match(r'^[A-Z\s]+$', line)):  # Não tudo maiúsculo
                                data['title'] = line[:80]  # Limitar tamanho
                                break
                except:
                    pass  # Ignorar erro na extração de texto
    except:
        pass  # Ignorar qualquer erro no fallback
    
    return data


# ------------------------------ Consultas às APIs ------------------------------

def google_books_search(query: str, api_key: Optional[str] = None, lang: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Busca na Google Books API"""
    base = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": query, "maxResults": 5}
    if lang:
        params["langRestrict"] = lang
    if api_key:
        params["key"] = api_key
    try:
        r = requests.get(base, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        items = data.get('items') or []
        best = None
        best_score = 0.0
        for it in items:
            info = it.get('volumeInfo', {})
            title = info.get('title') or ''
            authors = info.get('authors') or []
            full = f"{title} {' '.join(authors)}"
            score = token_score(full, query)
            if score > best_score:
                best_score = score
                best = info
        return best
    except Exception as e:
        print(f"Erro Google Books search: {e}")
        return None

def open_library_search(query: str) -> Optional[Dict[str, Any]]:
    """Busca na Open Library"""
    url = "https://openlibrary.org/search.json"
    try:
        r = requests.get(url, params={"q": query, "limit": 5}, timeout=20)
        r.raise_for_status()
        data = r.json()
        docs = data.get('docs') or []
        best = None
        best_score = 0.0
        for d in docs:
            title = d.get('title') or ''
            authors = d.get('author_name') or []
            full = f"{title} {' '.join(authors)}"
            score = token_score(full, query)
            if score > best_score:
                best_score = score
                best = d
        if not best:
            return None
        norm = {
            'title': best.get('title'),
            'authors': best.get('author_name') or [],
            'publishedDate': str(best.get('first_publish_year')) if best.get('first_publish_year') else None,
            'categories': best.get('subject')[:3] if best.get('subject') else None,
        }
        cover_id = best.get('cover_i')
        if cover_id:
            norm['imageLinks'] = {
                'thumbnail': f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg",
                'small': f"https://covers.openlibrary.org/b/id/{cover_id}-S.jpg",
                'large': f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg",
            }
        return norm
    except Exception as e:
        print(f"Erro Open Library search: {e}")
        return None

def merge_metadata(local: Dict[str, Any], api: Dict[str, Any]) -> Dict[str, Any]:
    """Mescla metadados locais com dados da API de forma inteligente"""
    merged = local.copy() if local else {}
    
    # Priorizar dados da API quando disponíveis
    if api:
        # Title - usar API se for melhor
        api_title = api.get('title')
        local_title = merged.get('title')
        if api_title and (not local_title or len(api_title) > len(local_title)):
            merged['title'] = api_title
        
        # Authors - juntar e remover duplicatas
        api_authors = api.get('authors', [])
        local_authors = merged.get('authors', [])
        if api_authors:
            all_authors = list(dict.fromkeys(local_authors + api_authors))
            merged['authors'] = all_authors
        
        # Year - preferir API
        api_year = api.get('publishedDate')
        if api_year:
            merged['publishedDate'] = api_year
        
        # Categories - juntar
        api_categories = api.get('categories', [])
        local_categories = merged.get('categories', [])
        if api_categories:
            all_categories = list(dict.fromkeys(local_categories + api_categories))
            merged['categories'] = all_categories
        
        # ImageLinks - preferir API
        api_images = api.get('imageLinks', {})
        if api_images:
            merged['imageLinks'] = api_images
    
    return merged

# ------------------------------ Organização e arquivo ------------------------------

def choose_primary_author(authors: Optional[List[str]]) -> str:
    """Seleciona e formata o autor principal de forma inteligente"""
    if not authors:
        return "Autor Desconhecido"
    
    # Pegar primeiro autor
    author = authors[0]
    
    # Corrigir formatação comum
    if ',' in author:
        parts = [p.strip() for p in author.split(',')]
        if len(parts) >= 2:
            # Formato "Sobrenome, Nome" -> "Nome Sobrenome"
            author = f"{parts[1]} {parts[0]}"
    
    # Remover lixo comum
    author = re.sub(r'\(.*?\)', '', author)  # Remover parênteses
    author = re.sub(r'\s+', ' ', author).strip()
    
    # Validar se é um autor plausível
    if (len(author) < 3 or 
        author.lower() in ['unknown', 'anonymous', 'anon', 'none', 'autor desconhecido'] or
        re.match(r'^[\d\W]+$', author)):
        return "Autor Desconhecido"
    
    return normalize_spaces(author)

def choose_primary_genre(categories: Optional[List[str]]) -> str:
    """Seleciona o gênero principal"""
    if not categories:
        return "Geral"
    cats = sorted(categories, key=lambda c: len(c))
    return sanitize_filename(cats[0]) or "Geral"

def build_filename(meta: Dict[str, Any], original_ext: str, pattern: str = "{author} - {title} ({year})") -> str:
    """Constrói nome do arquivo baseado nos metadados, mantendo a extensão original"""
    author = choose_primary_author(meta.get('authors'))
    title = meta.get('title') or "Sem Título"
    year = year_from_date_str(meta.get('publishedDate')) or "s.d."
    
    # Garantir que a extensão seja a original
    if not original_ext:
        original_ext = '.unknown'
    
    raw = pattern.format(author=author, title=title, year=year)
    return sanitize_filename(raw) + original_ext.lower()

def ensure_unique_path(base_dir: str, filename: str) -> str:
    """Garante que o caminho seja único - move para pasta de duplicados"""
    dest = os.path.join(base_dir, filename)
    if not os.path.exists(dest):
        return dest
    
    duplicates_dir = os.path.join(os.path.dirname(base_dir), 
                                 get_config_value(load_config(), 'Geral', 'duplicates_dirname', '3. Duplicados'))
    os.makedirs(duplicates_dir, exist_ok=True)
    
    return os.path.join(duplicates_dir, filename)

def download_cover(image_links: Dict[str, Any], dest_dir: str, base_name: str, logfn, fonte: str) -> Optional[str]:
    """Faz download da capa do livro"""
    urls = []
    if not image_links:
        return None
    for k in ["large", "thumbnail", "small"]:
        u = image_links.get(k)
        if u:
            urls.append(u)
    for url in urls:
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            os.makedirs(dest_dir, exist_ok=True)
            ext = '.jpg'
            out = os.path.join(dest_dir, sanitize_filename(base_name) + ext)
            with open(out, 'wb') as f:
                f.write(r.content)
            logfn(f"Capa baixada de {fonte}: {out}", "success")
            return out
        except Exception as e:
            logfn(f"Erro ao baixar capa {url}: {e}", "error")
            continue
    return None

@dataclass
class ActionLog:
    source_path: str
    dest_path: str
    title: str
    author: str
    year: str
    genre: str
    cover_path: str
    status: str
    note: str
    fonte: str

# ------------------------------ Worker ------------------------------
# Função principal de processamento de arquivo individual
def process_file(path: str,
                 out_base: str,
                 organize_mode: str,
                 pattern: str,
                 download_covers: bool,
                 api_key: Optional[str],
                 lang_restrict: Optional[str],
                 remover_acentos_flag: bool,
                 limpar_caracteres_flag: bool,
                 logfn) -> ActionLog:
    """Processa um arquivo de livro seguindo o fluxo CORRETO"""

    # Verificar se o arquivo existe
    if not os.path.exists(path):
        logfn(f"AVISO: Arquivo não encontrado: {os.path.basename(path)}", "warning")
        return ActionLog(
            source_path=path,
            dest_path="",
            title="Arquivo não encontrado",
            author="",
            year="",
            genre="",
            cover_path="",
            status="skipped",
            note="Arquivo não existe",
            fonte="Sistema"
        )

    ext = os.path.splitext(path)[1].lower()
    filename = os.path.basename(path)
    fonte = "Não identificado"
    meta = {}
    has_sufficient_metadata = False
    isbn = None

    logfn(f"=== PROCESSANDO: {filename} ===", "info")

    # === 1. EXTRAIR ISBN ===
    logfn("Extraindo ISBN do arquivo...", "info")
    extracted_isbn = extract_isbn_rigorous(path)
    
    if extracted_isbn:
        logfn(f"ISBN encontrado: {extracted_isbn}", "info")
        isbn_result = search_by_isbn(extracted_isbn, api_key)
        if isbn_result and isbn_result.get('score', 0) > 0.8:
            meta = isbn_result
            fonte = isbn_result.get("fonte", "ISBN")
            has_sufficient_metadata = True
            isbn = extracted_isbn
            logfn(f"✓ Livro identificado por ISBN: {meta.get('title', 'Sem título')}", "success")
        else:
            logfn(f"✗ ISBN {extracted_isbn} não retornou resultados válidos", "warning")
            isbn = None
    else:
        logfn("ISBN não localizado", "info")

    # === 2. CONSULTAR API COM METADADOS LOCAIS ===
    if not has_sufficient_metadata:
        logfn("Extraindo metadados para consulta API...", "info")
        local_meta = extract_local_metadata(path, ext)
        
        # Abordagem 1: METADADOS LOCAIS (limpos mas não fatiados)
        metadata_search_done = False
        if local_meta and local_meta.get('title'):
            title = clean_search_query_metadados(local_meta['title'])
            author = None
            if local_meta.get('authors') and local_meta['authors'][0]:
                author = clean_search_query_metadados(local_meta['authors'][0])
            
            logfn(f"Pesquisando com metadados - Título: '{title}', Autor: '{author}'", "info")
            
            # Pesquisar com metadados limpos
            gb_result = buscar_google_books(title, author, api_key)
            if gb_result:
                meta = gb_result
                fonte = "Google Books (Metadados)"
                has_sufficient_metadata = validate_metadata(meta, fonte)
                if has_sufficient_metadata:
                    logfn(f"✓ Identificado via metadados: {gb_result.get('title')}", "success")
                else:
                    logfn("✗ Metadados da API insuficientes, tentando nome do arquivo...", "warning")
                    meta = {}  # Reset para tentar nome do arquivo
            metadata_search_done = True
        
        # Abordagem 2: NOME DO ARQUIVO (se metadados não forem suficientes)
        if not has_sufficient_metadata:
            name_only = os.path.splitext(filename)[0]
            clean_name = clean_search_query_nome_arquivo(name_only)
            
            logfn(f"Pesquisando com nome do arquivo: '{clean_name}'", "info")
            
            # Tentar extrair título e autor do nome do arquivo
            title_from_name, author_from_name = extract_title_author_from_filename(clean_name)
            
            if title_from_name:
                logfn(f"Título extraído: '{title_from_name}', Autor: '{author_from_name}'", "info")
                # Pesquisar com título e autor extraídos
                gb_result = buscar_google_books(title_from_name, author_from_name, api_key)
                if gb_result:
                    meta = gb_result
                    fonte = "Google Books (Nome Arquivo)"
                    has_sufficient_metadata = validate_metadata(meta, fonte)
                    if has_sufficient_metadata:
                        logfn(f"✓ Identificado via nome arquivo: {gb_result.get('title')}", "success")
            
            # Se ainda não encontrou, tentar pesquisa genérica com nome limpo
            if not has_sufficient_metadata:
                gb_result = buscar_google_books(clean_name, None, api_key)
                if gb_result:
                    meta = gb_result
                    fonte = "Google Books (Nome Arquivo)"
                    has_sufficient_metadata = validate_metadata(meta, fonte)
                    if has_sufficient_metadata:
                        logfn(f"✓ Identificado via pesquisa genérica: {gb_result.get('title')}", "success")

    # === 3. VALIDAÇÃO FINAL ===
    has_sufficient_metadata = validate_metadata(meta, fonte)
    
    if not has_sufficient_metadata:
        logfn("=== RESULTADO: Nenhum resultado válido da API ===", "warning")
        # ... (código para mover para não localizados) ...
        logfn("=== RESULTADO: Metadados insuficientes ===", "warning")
        config = load_config()
        unknown_dir = get_config_value(config, 'Geral', 'unknown_dirname', '2. Não Localizados')
        dest_dir = os.path.join(out_base, unknown_dir)
        os.makedirs(dest_dir, exist_ok=True)
        
        clean_name = normalize_unknown_filename(filename)
        dest_path = os.path.join(dest_dir, clean_name)
        
        try:
            shutil.move(path, dest_path)
            logfn(f"✗ Movido para: {unknown_dir}/{clean_name}", "warning")
            
            return ActionLog(
                source_path=path,
                dest_path=dest_path,
                title=os.path.splitext(filename)[0],
                author="Desconhecido",
                year="s.d.",
                genre="Não Localizado",
                cover_path="",
                status="moved_to_unknown",
                note=f"Fonte: {fonte}, ISBN tentado: {isbn}",
                fonte=fonte
            )
        except Exception as e:
            logfn(f"ERRO: Falha ao mover para não localizados: {e}", "error")
            return ActionLog(
                source_path=path,
                dest_path=path,
                title=os.path.splitext(filename)[0],
                author="Desconhecido",
                year="s.d.",
                genre="Erro",
                cover_path="",
                status="error",
                note=str(e),
                fonte="Erro"
            )
    else:
        logfn("=== RESULTADO: Metadados confirmados pela API ===", "success")

    # === 4. PROCESSAMENTO FINAL ===
    meta = apply_text_normalization(meta, remover_acentos_flag, limpar_caracteres_flag)

    # Log detalhado
    logfn("=== METADADOS CONFIRMADOS PELA API ===", "success")
    logfn(f"Título: {meta.get('title', 'Nenhum')}", "info")
    logfn(f"Autores: {', '.join(meta.get('authors', ['Nenhum']))}", "info")
    logfn(f"Ano: {meta.get('publishedDate', 'Nenhum')}", "info")
    logfn(f"Gêneros: {', '.join(meta.get('categories', ['Nenhum']))}", "info")
    logfn(f"Fonte: {fonte}", "info")
    logfn("============================", "info")

    # Determinar destino
    author = choose_primary_author(meta.get('authors')) if meta.get('authors') else "Autor Desconhecido"
    genre = choose_primary_genre(meta.get('categories')) if meta.get('categories') else "Geral"
    year = year_from_date_str(meta.get('publishedDate')) or "s.d."
    title = meta.get('title') or os.path.splitext(filename)[0]

    if organize_mode == 'autor':
        dest_dir = os.path.join(out_base, sanitize_filename(author))
        logfn(f"Organizando por autor: {author}", "info")
    else:
        dest_dir = os.path.join(out_base, sanitize_filename(genre), sanitize_filename(author))
        logfn(f"Organizando por gênero/autor: {genre}/{author}", "info")

    os.makedirs(dest_dir, exist_ok=True)

    dest_name = build_filename({
        'authors': [author],
        'title': title,
        'publishedDate': year
    }, ext, pattern=pattern)
    
    dest_path = ensure_unique_path(dest_dir, dest_name)
    logfn(f"Destino: {os.path.relpath(dest_path, out_base)}", "info")

    # Baixar capa
    cover_path = ""
    if download_covers and has_sufficient_metadata:
        config = load_config()
        covers_dir = get_config_value(config, 'Geral', 'covers_dirname', 'covers')
        covers_full_dir = os.path.join(dest_dir, covers_dir)
        base_cover_name = os.path.splitext(os.path.basename(dest_path))[0]
        
        if meta.get('imageLinks'):
            cp = download_cover(meta.get('imageLinks'), covers_full_dir, base_cover_name, logfn, fonte)
            cover_path = cp or ""

    # Mover arquivo
    try:
        shutil.move(path, dest_path)
        status = 'moved'
        note = f'Fonte: {fonte}'
        if isbn:
            note += f', ISBN: {isbn}'
        logfn(f"✅ SUCESSO: Movido para {os.path.relpath(dest_path, out_base)}", "success")
    except Exception as e:
        status = 'error'
        note = f"Erro: {str(e)}"
        logfn(f"❌ ERRO: Falha ao mover arquivo: {e}", "error")
        dest_path = path

    return ActionLog(
        source_path=path,
        dest_path=dest_path,
        title=title,
        author=author,
        year=year,
        genre=genre,
        cover_path=cover_path,
        status=status,
        note=note,
        fonte=fonte
    )
    
# === Interface Tkinter ===
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Organizador de Livros - Automação Total")
        self.geometry("1000x750")

        # Carregar configuração
        self.config = load_config()
        
        # Variáveis da interface
        self.src_var = tk.StringVar(value=get_config_value(self.config, 'Pastas', 'pasta_origem', ''))
        self.dst_var = tk.StringVar(value=get_config_value(self.config, 'Pastas', 'pasta_destino', ''))
        self.mode_var = tk.StringVar(value=get_config_value(self.config, 'Geral', 'organize_mode', 'autor'))
        self.pattern_var = tk.StringVar(value=get_config_value(self.config, 'Geral', 'filename_pattern', '{author} - {title} ({year})'))
        self.covers_var = tk.BooleanVar(value=get_config_value(self.config, 'Opcoes', 'baixar_capas', 'True').lower() == 'true')
        self.key_var = tk.StringVar(value=get_config_value(self.config, 'API', 'google_books_key', ''))
        self.lang_var = tk.StringVar(value=get_config_value(self.config, 'Geral', 'language', 'pt'))
        self.remover_acentos_var = tk.BooleanVar(value=get_config_value(self.config, 'Opcoes', 'remover_acentos', 'True').lower() == 'true')
        self.limpar_caracteres_var = tk.BooleanVar(value=get_config_value(self.config, 'Opcoes', 'limpar_caracteres', 'True').lower() == 'true')
        self.ignorar_sem_meta_var = tk.BooleanVar(value=get_config_value(self.config, 'Opcoes', 'ignorar_sem_metadados', 'False').lower() == 'true')

        self.queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.total_files = 0
        self.processed_files = 0

        self.create_widgets()
        
        # Chamar teste de APIs após um pequeno delay para garantir que a interface esteja pronta
        self.after(100, self.test_apis)
    
    def create_widgets(self):
        pad = {'padx': 8, 'pady': 6}
        frm = ttk.Frame(self)
        frm.pack(fill='both', expand=True)

        # Linha 1: Pasta origem
        row1 = ttk.Frame(frm)
        row1.pack(fill='x', **pad)
        ttk.Label(row1, text="Pasta de livros (origem):").pack(side='left')
        ttk.Entry(row1, textvariable=self.src_var, width=70).pack(side='left', padx=6)
        ttk.Button(row1, text="Selecionar", command=self.choose_src).pack(side='left')

        # Linha 2: Pasta destino
        row2 = ttk.Frame(frm)
        row2.pack(fill='x', **pad)
        ttk.Label(row2, text="Pasta destino (biblioteca organizada):").pack(side='left')
        ttk.Entry(row2, textvariable=self.dst_var, width=68).pack(side='left', padx=6)
        ttk.Button(row2, text="Selecionar", command=self.choose_dst).pack(side='left')

        # Linha 3: Modo de organização
        row3 = ttk.Frame(frm)
        row3.pack(fill='x', **pad)
        ttk.Label(row3, text="Organizar por:").pack(side='left')
        ttk.Radiobutton(row3, text="Autor", value='autor', variable=self.mode_var).pack(side='left')
        ttk.Radiobutton(row3, text="Gênero / Autor", value='genero', variable=self.mode_var).pack(side='left')

        # Linha 4: Padrão de nome
        row4 = ttk.Frame(frm)
        row4.pack(fill='x', **pad)
        ttk.Label(row4, text="Padrão do nome do arquivo:").pack(side='left')
        ttk.Entry(row4, textvariable=self.pattern_var, width=50).pack(side='left', padx=6)
        ttk.Label(row4, text="Campos: {author}, {title}, {year}").pack(side='left')

        # Linha 5: Opções de texto
        row5 = ttk.Frame(frm)
        row5.pack(fill='x', **pad)
        ttk.Checkbutton(row5, text="Remover acentos", variable=self.remover_acentos_var).pack(side='left')
        ttk.Checkbutton(row5, text="Limpar caracteres especiais", variable=self.limpar_caracteres_var).pack(side='left', padx=10)
        ttk.Checkbutton(row5, text="Ignorar sem metadados", variable=self.ignorar_sem_meta_var).pack(side='left')

        # Linha 6: Capas e API
        row6 = ttk.Frame(frm)
        row6.pack(fill='x', **pad)
        ttk.Checkbutton(row6, text="Baixar capas", variable=self.covers_var).pack(side='left')
        ttk.Label(row6, text="Idioma:").pack(side='left', padx=(20, 4))
        ttk.Entry(row6, textvariable=self.lang_var, width=6).pack(side='left')
        ttk.Label(row6, text="Google Books API Key:").pack(side='left', padx=(20, 4))
        ttk.Entry(row6, textvariable=self.key_var, width=30).pack(side='left')

        # Linha 7: Botões de configuração
        row7 = ttk.Frame(frm)
        row7.pack(fill='x', **pad)
        ttk.Button(row7, text="Salvar Configurações", command=self.save_all_config).pack(side='left')
        ttk.Button(row7, text="Resetar Configurações", command=self.reset_config).pack(side='left', padx=6)
        ttk.Button(row7, text="Testar Conexão APIs", command=self.test_apis).pack(side='left', padx=6)
        
        # Linha 8: Botões adicionais
        row8 = ttk.Frame(frm)
        row8.pack(fill='x', **pad)
        ttk.Button(row8, text="Não Localizados", command=self.show_unknown_files).pack(side='left')

        # Barra de progresso
        self.progress = ttk.Progressbar(frm, orient='horizontal', mode='determinate')
        self.progress.pack(fill='x', padx=8, pady=8)

        # Botões de ação
        actions = ttk.Frame(frm)
        actions.pack(fill='x', **pad)
        ttk.Button(actions, text="Executar", command=self.start_processing).pack(side='left')
        ttk.Button(actions, text="Parar", command=self.stop_processing).pack(side='left', padx=6)

        # Log visual com tags de cores
        self.log = tk.Text(frm, height=18, wrap=tk.WORD)
        self.log.pack(fill='both', expand=True, padx=8, pady=8)
        self.log.configure(state='disabled')
        
        # Configurar tags para cores
        self.log.tag_configure("success", foreground="green")
        self.log.tag_configure("error", foreground="red")
        self.log.tag_configure("warning", foreground="orange")
        self.log.tag_configure("info", foreground="blue")
        self.log.tag_configure("debug", foreground="gray")
    
    def save_all_config(self):
        """Salva todas as configurações atuais"""
        self.config.set('Pastas', 'pasta_origem', self.src_var.get())
        self.config.set('Pastas', 'pasta_destino', self.dst_var.get())
        self.config.set('Geral', 'organize_mode', self.mode_var.get())
        self.config.set('Geral', 'filename_pattern', self.pattern_var.get())
        self.config.set('Geral', 'language', self.lang_var.get())
        self.config.set('Opcoes', 'baixar_capas', str(self.covers_var.get()))
        self.config.set('Opcoes', 'remover_acentos', str(self.remover_acentos_var.get()))
        self.config.set('Opcoes', 'limpar_caracteres', str(self.limpar_caracteres_var.get()))
        self.config.set('Opcoes', 'ignorar_sem_metadados', str(self.ignorar_sem_meta_var.get()))
        self.config.set('API', 'google_books_key', self.key_var.get())
        
        save_config(self.config)
        self.log_line("✓ Todas as configurações salvas com sucesso!", "success")
    
    def reset_config(self):
        """Reseta para configurações padrão"""
        if messagebox.askyesno("Confirmar", "Tem certeza que deseja resetar todas as configurações para os valores padrão?"):
            delete_config()
            self.config = load_config()
            
            # Resetar variáveis da interface
            self.src_var.set('')
            self.dst_var.set('')
            self.mode_var.set('autor')
            self.pattern_var.set('{author} - {title} ({year})')
            self.covers_var.set(True)
            self.key_var.set('')
            self.lang_var.set('pt')
            self.remover_acentos_var.set(True)
            self.limpar_caracteres_var.set(True)
            self.ignorar_sem_meta_var.set(False)
            
            self.log_line("✓ Configurações resetadas para padrão!", "success")
    
    def test_apis(self):
        """Testa conexão com as APIs e exibe no log"""
        # Usar print inicialmente até a interface estar pronta
        print("=== TESTE DE CONEXÃO ===")
        
        internet_ok = test_internet_connection()
        if internet_ok:
            print("✓ Conexão com internet: OK")
        else:
            print("✗ Conexão com internet: FALHA")
            # Tentar logar na interface se estiver disponível
            try:
                self.log_line("✗ Conexão com internet: FALHA", "error")
            except:
                pass
            return
            
        api_key = self.key_var.get().strip() or None
        gb_ok, gb_msg = test_google_books_api(api_key)
        if gb_ok:
            print(f"✓ {gb_msg}")
        else:
            print(f"✗ {gb_msg}")
            
        ol_ok, ol_msg = test_open_library()
        if ol_ok:
            print(f"✓ {ol_msg}")
        else:
            print(f"✗ {ol_msg}")
        
        print("=== FIM DO TESTE ===\n")
        
        # Agora tentar atualizar a interface se estiver pronta
        try:
            self.log_line("=== TESTE DE CONEXÃO ===", "info")
            if internet_ok:
                self.log_line("✓ Conexão com internet: OK", "success")
            else:
                self.log_line("✗ Conexão com internet: FALHA", "error")
                
            if gb_ok:
                self.log_line(f"✓ {gb_msg}", "success")
            else:
                self.log_line(f"✗ {gb_msg}", "error")
                
            if ol_ok:
                self.log_line(f"✓ {ol_msg}", "success")
            else:
                self.log_line(f"✗ {ol_msg}", "error")
                
            self.log_line("=== FIM DO TESTE ===\n", "info")
        except Exception as e:
            print(f"Erro ao atualizar interface: {e}")
    
    def choose_src(self):
        d = filedialog.askdirectory(title="Selecione a pasta de origem")
        if d:
            self.src_var.set(d)
    
    def choose_dst(self):
        d = filedialog.askdirectory(title="Selecione a pasta de destino")
        if d:
            self.dst_var.set(d)
    
    def show_unknown_files(self):
        """Mostra mensagem para função não implementada"""
        messagebox.showinfo("Não Localizados", 
                           "Função ainda não implementada.\n\n"
                           "Esta funcionalidade permitirá gerenciar os arquivos "
                           "que não foram identificados automaticamente.")
    
    def start_processing(self):
        src = self.src_var.get().strip()
        dst = self.dst_var.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showerror("Erro", "Pasta de origem inválida.")
            return
        if not dst:
            messagebox.showerror("Erro", "Informe a pasta de destino.")
            return
        
        # Testar conexão com APIs antes de começar
        self.log_line("=== TESTANDO CONEXÃO COM APIs ===", "info")
        google_ok, ol_ok = test_api_connection()
        
        if google_ok:
            self.log_line("✓ Google Books API: Online", "success")
        else:
            self.log_line("✗ Google Books API: Offline", "error")
            
        if ol_ok:
            self.log_line("✓ Open Library: Online", "success")
        else:
            self.log_line("✗ Open Library: Offline", "error")
            
        if not google_ok and not ol_ok:
            self.log_line("AVISO: Todas as APIs estão offline - usando apenas metadados locais", "warning")
        
        self.log_line("", "info")
        
        os.makedirs(dst, exist_ok=True)
        self.stop_flag.clear()
        self.processed_files = 0

        files = []
        for root, _, fnames in os.walk(src):
            for fn in fnames:
                ext = os.path.splitext(fn)[1].lower()
                if ext in SUPPORTED_EXTS:
                    files.append(os.path.join(root, fn))
        if not files:
            messagebox.showinfo("Nada a fazer", "Nenhum arquivo suportado encontrado.")
            return

        self.total_files = len(files)
        self.progress.configure(maximum=self.total_files, value=0)
        self.clear_log()
        self.log_line(f"Arquivos encontrados: {self.total_files}", "info")
        self.log_line("", "info")

        t = threading.Thread(target=self.worker, args=(files,), daemon=True)
        t.start()
        self.after(200, self.drain_queue)
    
    def stop_processing(self):
        self.stop_flag.set()
        self.log_line("⏹ Solicitação de cancelamento recebida...", "warning")
    
    def worker(self, files: List[str]):
        """Thread worker para processamento de arquivos"""
        
        # Criar uma função wrapper para logging thread-safe
        def log_wrapper(text: str, tag: str = ""):
            self.queue.put(("log", (text, tag)))
        
        config = load_config()
        out_base = self.dst_var.get().strip()
        mode = self.mode_var.get()
        pattern = self.pattern_var.get()
        covers = self.covers_var.get()
        api_key = self.key_var.get().strip() or None
        lang = self.lang_var.get().strip() or None
        remover_acentos_flag = self.remover_acentos_var.get()
        limpar_caracteres_flag = self.limpar_caracteres_var.get()

        # Usar nomes de pastas da configuração
        log_dirname = get_config_value(config, 'Geral', 'log_dirname', '1. logs')
        unknown_dirname = get_config_value(config, 'Geral', 'unknown_dirname', '2. Não Localizados')
        duplicates_dirname = get_config_value(config, 'Geral', 'duplicates_dirname', '3. Duplicados')
        covers_dirname = get_config_value(config, 'Geral', 'covers_dirname', 'covers')

        # Criar pastas especiais
        os.makedirs(os.path.join(out_base, log_dirname), exist_ok=True)
        os.makedirs(os.path.join(out_base, unknown_dirname), exist_ok=True)
        os.makedirs(os.path.join(out_base, duplicates_dirname), exist_ok=True)

        # Preparar logs CSV
        log_dir = os.path.join(out_base, log_dirname)
        actions_csv = os.path.join(log_dir, "organizacao_log.csv")
        index_csv = os.path.join(log_dir, "biblioteca_index.csv")

        actions: List[ActionLog] = []
        library_rows: List[List[str]] = []

        # Filtrar arquivos que ainda existem (não foram processados anteriormente)
        existing_files = [f for f in files if os.path.exists(f)]
        
        if len(existing_files) != len(files):
            log_wrapper(f"AVISO: {len(files) - len(existing_files)} arquivos já foram processados anteriormente", "warning")

        for i, path in enumerate(existing_files, 1):
            if self.stop_flag.is_set():
                log_wrapper("⏹ Processamento cancelado pelo usuário", "warning")
                break
            try:
                alog = process_file(
                    path=path,
                    out_base=out_base,
                    organize_mode=mode,
                    pattern=pattern,
                    download_covers=covers,
                    api_key=api_key,
                    lang_restrict=lang,
                    remover_acentos_flag=remover_acentos_flag,
                    limpar_caracteres_flag=limpar_caracteres_flag,
                    logfn=log_wrapper,  # Usar a wrapper function
                )
                actions.append(alog)
                library_rows.append([
                    alog.title,
                    alog.author,
                    alog.year,
                    alog.genre,
                    os.path.relpath(alog.dest_path, out_base) if alog.dest_path else '',
                    os.path.relpath(alog.cover_path, out_base) if alog.cover_path else '',
                    alog.fonte
                ])
            except Exception as e:
                error_msg = f"ERRO CRÍTICO: Falha inesperada com '{os.path.basename(path)}': {str(e)}"
                log_wrapper(error_msg, "error")
                print(traceback.format_exc())

            # Atualizar progresso
            self.processed_files = i
            self.queue.put(("progress", i))

        # Gravar CSVs
        try:
            with open(actions_csv, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_ALL)
                w.writerow(["source_path", "dest_path", "title", "author", "year", "genre", "cover_path", "status", "note", "fonte"])
                for a in actions:
                    w.writerow([
                        a.source_path, a.dest_path, a.title, a.author, a.year, a.genre, 
                        a.cover_path, a.status, a.note, a.fonte
                    ])
            self.queue.put(("log", (f"✓ Log de ações salvo: {actions_csv}", "success")))
        except Exception as e:
            self.queue.put(("log", (f"ERRO: Ao salvar log de ações: {e}", "error")))

        try:
            with open(index_csv, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_ALL)
                w.writerow(["title", "author", "year", "genre", "relative_path", "cover_relpath", "fonte"])
                for row in library_rows:
                    w.writerow(row)
            self.queue.put(("log", (f"✓ Índice da biblioteca salvo: {index_csv}", "success")))
        except Exception as e:
            self.queue.put(("log", (f"ERRO: Ao salvar índice: {e}", "error")))

        self.queue.put(("done", None))
    
    def drain_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == 'progress':
                    self.progress.configure(value=payload)
                elif kind == 'log':
                    text, tag = payload
                    self.append_log(text, tag)
                elif kind == 'done':
                    self.progress.configure(value=self.total_files)
                    self.log_line("✅ Processamento concluído!", "success")
        except queue.Empty:
            pass
        if not self.stop_flag.is_set() and self.processed_files < self.total_files:
            self.after(200, self.drain_queue)
    
    def append_log(self, text: str, tag: str = ""):
        """Adiciona texto ao widget de log"""
        try:
            self.log.configure(state='normal')
            if tag:
                self.log.insert('end', text + "\n", tag)
            else:
                self.log.insert('end', text + "\n")
            self.log.see('end')
            self.log.configure(state='disabled')
        except Exception as e:
            print(f"Erro no append_log: {e} - Texto: {text}")
    
    def clear_log(self):
        """Limpa o widget de log"""
        try:
            self.log.configure(state='normal')
            self.log.delete('1.0', 'end')
            self.log.configure(state='disabled')
        except Exception as e:
            print(f"Erro ao limpar log: {e}")
    
    def log_line(self, text: str, tag: str = ""):
        """Adiciona uma linha ao log de forma segura"""
        try:
            self.append_log(text, tag)
        except Exception as e:
            print(f"Erro no log_line: {e} - Texto: {text}")
    
#   def log_line_threadsafe(self, text: str, tag: str = ""):
#       """Adiciona timestamp e formatação melhorada ao log"""
#       timestamp = time.strftime("%H:%M:%S")
#       formatted_text = f"[{timestamp}] {text}"
#       self.queue.put(("log", (formatted_text, tag)))

if __name__ == '__main__':
    app = App()
    app.mainloop()