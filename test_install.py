
## Arquivo de exemplo simples para testar

**test_install.py**:
```python
#!/usr/bin/env python3
"""
Teste simples para verificar se o Livrando está funcionando
"""

try:
    from Livrando import __version__, __author__
    print(f"✅ Livrando {__version__} por {__author__} carregado com sucesso!")
    
    # Testar dependências
    import requests
    import ebooklib
    import PyPDF2
    from PIL import Image
    
    print("✅ Todas as dependências estão instaladas!")
    
except ImportError as e:
    print(f"❌ Erro de importação: {e}")
    print("Instale as dependências com: pip install -r requirements.txt")
    
except Exception as e:
    print(f"❌ Erro inesperado: {e}")