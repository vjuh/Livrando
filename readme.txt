Aqui estão as instruções completas e o requirements.txt para rodar o script:

✅ 1. Criar um ambiente virtual (opcional, mas recomendado)

No terminal ou prompt:
python -m venv venv

Ativar:
Windows:
venv\Scripts\activate

Linux/macOS:
source venv/bin/activate

✅ 2. Criar o arquivo requirements.txt

Conteúdo:

requests
tkintertable
ebooklib
PyPDF2
pillow
[instalar assim: pip install (item)]

✅ 3. Instalar dependências
pip install -r requirements.txt

✅ 4. Gerar uma chave para a Google Books API (opcional, mas melhora os resultados)

Acesse: Google Cloud Console

Crie um projeto e ative a Google Books API.

Gere uma API Key.

Cole no campo da interface Tkinter quando rodar o script (ou deixe vazio para usar apenas Open Library).

✅ 5. Executar o script
python seu_script.py


A janela do Tkinter vai abrir com:

Botão para escolher a pasta.

Campo para escolher se organiza por Autor ou por Gênero/Autor.

Opção para baixar capas.

Campo para API Key do Google Books (opcional).

Botão Iniciar para processar.

✅ 6. Estrutura final

Depois de rodar, você terá:

/Livros_Organizados/
    /Autor/
        Nome do Livro (Ano).epub
/covers/
    Nome do Livro.jpg
log.csv
biblioteca_index.html