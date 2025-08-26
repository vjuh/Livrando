# Livrando - Organizador Automático de Livros

![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Stable-brightgreen.svg)

Organizador inteligente de livros digitais que automaticamente extrai metadados, renomeia arquivos e organiza em pastas por autor ou gênero.

## ✨ Funcionalidades

- 📚 Suporte a múltiplos formatos: EPUB, PDF, MOBI, AZW3, DJVU, DOCX, etc.
- 🔍 Extração inteligente de metadados de arquivos e APIs
- 📁 Organização automática por autor ou gênero/autor
- 🌐 Integração com Google Books API e Open Library
- 🖼️ Download automático de capas dos livros
- 🔄 Detecção e tratamento de arquivos duplicados
- 📊 Geração de logs e índice CSV da biblioteca
- 🎯 Interface gráfica intuitiva com Tkinter
- ⚡ Processamento em lote com barra de progresso

## 🚀 Instalação

### Pré-requisitos
- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

### Instalação das dependências

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/livrando.git
cd livrando

# Instale as dependências
pip install -r requirements.txt
```
#### Dependências principais
- requests - Requisições HTTP para APIs
- ebooklib - Leitura de arquivos EPUB
- PyPDF2 - Leitura de arquivos PDF
- Pillow - Manipulação de imagens para capas
- tkinter - Interface gráfica (já incluída no Python)

## 🏗️ Instalação como pacote (opcional)

Para instalar o Livrando como um pacote Python:

```bash
# Instalar a partir do código fonte
pip install .

# Ou instalar em modo desenvolvimento
pip install -e .

# Agora você pode executar com:
livrando
```

## 🐛 Solução de Problemas
```bash
# Se houver problemas com dependências:
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

```
## 📖 Como usar

1. Execute o programa:

```bash
python Livrando.py
```

2. Configure as pastas:
	- Selecione a pasta de origem (onde estão seus livros)
	- Selecione a pasta de destino (onde os livros organizados serão salvos)

3. Ajuste as opções (opcional):
	- Modo de organização: Autor ou Gênero/Autor
	- Padrão de nomeação dos arquivos
	- Opções de baixar capas e normalização de texto
	- Chave da API Google Books (opcional, melhora resultados)

4. Execute o processamento:
	- Clique em "Executar" para iniciar a organização
	- Acompanhe o progresso na barra e no log

5. Gerencie arquivos não identificados:
	- Use o botão "Não Localizados" para editar metadados manualmente
	- Processe novamente os arquivos editados

## Comandos para testar:

```bash
# Navegue até a pasta do projeto
cd livrando

# Instale em modo desenvolvimento (recomendado)
pip install -e .

# Teste se funciona
python -m livrando

# Ou execute diretamente
livrando

# Teste as importações
python test_install.py
```

## ⚙️ Configuração da API

Para melhores resultados, obtenha uma chave da Google Books API:

1. Acesse Google Cloud Console
2. Crie um projeto e ative a Books API
3. Gere uma chave de API
4. Cole a chave no campo apropriado no programa

## 📁 Estrutura de pastas resultante

``` text
biblioteca_organizada/
├── 1. logs/
│   ├── organizacao_log.csv
│   └── biblioteca_index.csv
├── 2. Não Localizados/
├── 3. Duplicados/
├── 4. Excluidos/
├── Autor 1/
│   ├── Autor 1 - Livro 1 (2020).epub
│   ├── Autor 1 - Livro 2 (2018).pdf
│   └── covers/
│       ├── Autor 1 - Livro 1 (2020).jpg
│       └── Autor 1 - Livro 2 (2018).jpg
├── Autor 2/
└── Gênero/
    ├── Autor 3/
    └── Autor 4/
```
## 🛠️ Desenvolvimento

- Estrutura do projeto

``` text
livrando/
├── Livrando.py          # Arquivo principal
├── __init__.py          # Para tratar como pacote
├── __main__.py          # Ponto de entrada
├── pyproject.toml       # Configuração moderna de build
├── requirements.txt     # Dependências
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── .gitignore
├── test_install.py      # Teste de instalação
└── examples/
    └── example_usage.py
``` 

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para detalhes.

## 🤝 Suporte

Encontrou um problema ou tem uma sugestão?

- Entre em contato pelo email: seu-email@exemplo.com

## 🙏 Agradecimentos

- Google Books API por fornecer metadados de livros
- Open Library por ser uma fonte alternativa aberta
- Comunidade Python por todas as bibliotecas incríveis

## ⭐️ Se este projeto foi útil para você, deixe uma estrela no GitHub!
