# gerenciador.py
import struct
import time
from constantes import *

# ==============================================================================
# FUNÇÕES AUXILIARES DE CONSTRUÇÃO (MONTAM OS DADOS NA MEMÓRIA)
# ==============================================================================

def _gerar_superbloco() -> bytes:
    blocos_livres = TOTAL_BLOCOS - INICIO_BLOCOS_DADOS - 1
    inodes_livres = TOTAL_INODES - 1
    
    return struct.pack(FORMATO_SUPERBLOCO, 
                       MAGIC_NUMBER, 
                       TOTAL_BLOCOS, 
                       blocos_livres, 
                       TOTAL_INODES, 
                       inodes_livres)

def _gerar_bitmap_inodes() -> bytes:
    """Monta o bitmap de i-nodes marcando apenas o i-node 0 (Raiz) como ocupado."""
    bitmap = bytearray(TAMANHO_BLOCO) # Cria um array com 2048 posições
                                     #e todas elas são inicializadas com o valor 0. 
    bitmap[0] |= (1 << 0)  # Bit 0 do Byte 0 = 1, marcando o i-node 0 como ocupado (raiz)
    return bytes(bitmap) # Converte o bytearray mutável em bytes imutável por causa do f.write

def _gerar_bitmap_blocos() -> bytes:
    """Monta o bitmap de blocos marcando do bloco 0 até o INICIO_BLOCOS_DADOS como ocupados."""
    bitmap = bytearray(QTD_BLOCOS_BITMAP_DADOS * TAMANHO_BLOCO) # Sequência de bytes MUTAVEL
    # inicializada com 0 (tamanho = 4 blocos * 2048 bytes = 8192 bytes)
    
    # Marca como ocupados: superbloco (0), bitmaps (1-5), tabela de inodes (6-517) e bloco da raiz (518)
    for bloco in range(INICIO_BLOCOS_DADOS + 1): # 0 A 518 (inclusive) = 519 blocos ocupado
        byte_idx = bloco // 8 #  Cada byte do bitmap é 8 blocos, então o índice do byte é o bloco dividido por 8
        bit_idx = bloco % 8
        bitmap[byte_idx] |= (1 << bit_idx)
        
    return bytes(bitmap) 
# A máscara é necessária pois se eu maracasse o bloco 518 eu apagaria os bits do bloco 512-517
# como em o alocar_blocos() em fs

def _gerar_inode_raiz() -> bytes:
    """Monta os 256 bytes do i-node da raiz (/)."""
    agora = int(time.time())
    apontadores = [INICIO_BLOCOS_DADOS] + [0] * 11  # Aponta para o bloco 518
    # struct.pack() vai empacotar os dados de acordo com o formato definido em FORMATO_INODE
    # b converte para bytes, e o resto são os campos do i-node raiz
    return struct.pack(FORMATO_INODE,
                       b'/', b'system', b'root',          # Nome, Criador, Dono
                       2 * TAMANHO_ENTRADA_DIR,           # Tamanho (2 entradas: . e .. de 64 bytes cada)
                       agora, agora,                      # Data criação e modificação
                       0o755,                             # Permissões (rwxr-xr-x). número em octal
                       *apontadores,                      # 12 ponteiros
                       TIPO_DIRETORIO,                    # Tipo
                       0,                                 # Próximo (0 = não é link / raiz não tem pai)
                       b'\0' * 48)                        # Padding

# b'/' -: 64 , b'system' -: 32 , b'root' -: 32 , 2 * TAMANHO_ENTRADA_DIR -: 4 , 
# agora -: 8 , agora -: 8 , 0o755 -: 4 , *apontadores -: 48 , TIPO_DIRETORIO -: 4 , 0 -: 4 , b'\0' * 48 -: 48

def _gerar_bloco_dados_raiz() -> bytes:
    """Monta o bloco de dados da raiz com as entradas '.' e '..' e sentinelas."""
    bloco = bytearray(TAMANHO_BLOCO) #bytearray é uma lista mutável de bytes, diferente de bytes que é imutável
    n_entradas = TAMANHO_BLOCO // TAMANHO_ENTRADA_DIR # entradas = 2048 / 64 = 32 entradas de 64 bytes cada
    
    # Preenche TODAS as entradas com a sentinela de inválido
    for i in range(n_entradas):
        off = i * TAMANHO_ENTRADA_DIR + 60
        bloco[off:off+4] = struct.pack('<I', I_NODE_INVALIDO)

    # Entrada 0: "." (aponta para a própria raiz, i-node 0)
    bloco[0:60] = b'.' + b'\0' * 59
    bloco[60:64] = struct.pack('<I', INODE_RAIZ)

    # Entrada 1: ".." (aponta para a própria raiz, i-node 0)
    bloco[64:124] = b'..' + b'\0' * 58
    bloco[124:128] = struct.pack('<I', INODE_RAIZ)
    
    return bytes(bloco)


# ==============================================================================
# FUNÇÃO PRINCIPAL 
# ==============================================================================

def formatar_disco(nome_disco: str = "disk.img"):
    """Formata o disco criando a estrutura inicial do sistema de arquivos."""
    print(f"Iniciando formatação do disco '{nome_disco}'...")
    
    # Criar o arquivo esparso (sparse file) de 128MB instantaneamente
    with open(nome_disco, 'wb') as f:
        f.seek(TAMANHO_DISCO - 1)
        f.write(b'\0')
    print(f"Arquivo de {TAMANHO_DISCO} bytes criado.")

    # Gerar todos os dados na memória RAM primeiro
    print("Montando estruturas de metadados na memória...")
    dados_superbloco = _gerar_superbloco()
    dados_bmp_inodes = _gerar_bitmap_inodes()
    dados_bmp_blocos = _gerar_bitmap_blocos()
    dados_inode_raiz = _gerar_inode_raiz()
    dados_bloco_raiz = _gerar_bloco_dados_raiz()

    # Gravar tudo no disco de forma organizada em um único bloco 'with'
    print("Gravando estruturas no disco...")
    with open(nome_disco, 'r+b') as f:
        f.seek(BLOCO_SUPERBLOCO * TAMANHO_BLOCO)
        f.write(dados_superbloco)
        
        f.seek(INICIO_BITMAP_BLOCOS * TAMANHO_BLOCO)
        f.write(dados_bmp_blocos)
        
        f.seek(INICIO_BITMAP_INODES * TAMANHO_BLOCO)
        f.write(dados_bmp_inodes)
        
        f.seek(INICIO_TABELA_INODES * TAMANHO_BLOCO)
        f.write(dados_inode_raiz)
        
        f.seek(INICIO_BLOCOS_DADOS * TAMANHO_BLOCO)
        f.write(dados_bloco_raiz)
        
    print("Formatação concluída. O disco está pronto para ser montado.")


if __name__ == "__main__":
    formatar_disco()