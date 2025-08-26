#!/usr/bin/env python3
"""
Exemplo de uso programático do Livrando

Este exemplo demonstra como usar as funcionalidades principais
do Livrando de forma programática, sem a interface gráfica.
"""

import os
import sys
from Livrando import process_file, load_config, get_config_value

def processar_pasta_automaticamente(pasta_origem, pasta_destino):
    """
    Processa todos os arquivos de uma pasta de forma automática
    
    Args:
        pasta_origem (str): Caminho da pasta com os arquivos
        pasta_destino (str): Caminho da pasta de destino
    """
    
    # Carregar configuração padrão
    config = load_config()
    
    # Configurar opções
    organize_mode = get_config_value(config, 'Geral', 'organize_mode', 'autor')
    pattern = get_config_value(config, 'Geral', 'filename_pattern', '{author} - {title} ({year})')
    download_covers = get_config_value(config, 'Opcoes', 'baixar_capas', 'True').lower() == 'true'
    api_key = get_config_value(config, 'API', 'google_books_key', '')
    lang = get_config_value(config, 'Geral', 'language', 'pt')
    remover_acentos = get_config_value(config, 'Opcoes', 'remover_acentos', 'True').lower() == 'true'
    limpar_caracteres = get_config_value(config, 'Opcoes', 'limpar_caracteres', 'True').lower() == 'true'
    
    # Função de logging simples
    def log_simples(texto, tag=""):
        print(f"[{tag.upper()}] {texto}" if tag else texto)
    
    # Processar todos os arquivos
    for arquivo in os.listdir(pasta_origem):
        caminho_completo = os.path.join(pasta_origem, arquivo)
        
        if os.path.isfile(caminho_completo):
            extensao = os.path.splitext(arquivo)[1].lower()
            
            if extensao in ['.epub', '.pdf', '.mobi', '.azw3']:
                print(f"\nProcessando: {arquivo}")
                
                try:
                    resultado = process_file(
                        path=caminho_completo,
                        out_base=pasta_destino,
                        organize_mode=organize_mode,
                        pattern=pattern,
                        download_covers=download_covers,
                        api_key=api_key,
                        lang_restrict=lang,
                        remover_acentos_flag=remover_acentos,
                        limpar_caracteres_flag=limpar_caracteres,
                        logfn=log_simples
                    )
                    
                    if resultado.status == 'moved':
                        print(f"✓ Sucesso: {resultado.title}")
                    else:
                        print(f"✗ Erro: {resultado.note}")
                        
                except Exception as e:
                    print(f"❌ Erro crítico: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python example_usage.py <pasta_origem> <pasta_destino>")
        sys.exit(1)
    
    origem = sys.argv[1]
    destino = sys.argv[2]
    
    if not os.path.exists(origem):
        print(f"Erro: Pasta de origem '{origem}' não existe")
        sys.exit(1)
    
    os.makedirs(destino, exist_ok=True)
    processar_pasta_automaticamente(origem, destino)