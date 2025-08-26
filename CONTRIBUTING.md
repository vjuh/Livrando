# Guia de Contribuição
============
Obrigado por considerar contribuir com o Livrando! Seguem algumas diretrizes:

## Como contribuir
============
1. **Reportar bugs**
   - Use o template de problemas para reportar bugs
   - Inclua informações do sistema
   - Adicione exemplos, quando possível

2. **Sugerir melhorias**
   - Descreva claramente
   - Explique o caso de uso
   - Mostre exemplos, se aplicável

3. **Enviar código**
   - Siga o estilo de código existente
   - Adicione testes quando possível
   - Atualize a documentação

## Setup de desenvolvimento
============
1. Faça fork do repositório
2. Clone seu fork:
   ```bash
   git clone https://github.com/vjuh/Livrando.git
   cd livrando
   ```
3. Crie um ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # ou
   venv\Scripts\activate     # Windows
   ```
4. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```
5. Instale em modo desenvolvimento:
   ```bash
   pip install -e .
   ```
   
   
   
Estilo de código
============
- Siga PEP 8
- Use type hints quando possível
- Documente funções com docstrings
- Mantenha testes atualizados

Estrutura do código
============
- Livrando.py - Arquivo principal com todas as funcionalidades
- Funções organizadas por responsabilidade
- Separação clara entre lógica e interface

Testes
============
   ``` bash
# Em breve suporte a testes automatizados
   ```
Pull Requests
============
1. Atualize sua branch com a main
2. Adicione testes se aplicável
3. Atualize a documentação
4. Verifique que todos os testes passam
5. Espere a revisão do código

Estrutura final do projeto:
============
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