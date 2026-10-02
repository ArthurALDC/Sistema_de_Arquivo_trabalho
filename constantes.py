# constantes.py
import struct

# =============================================================================
# Dimensões do disco (dados do enunciado)
# O bloco é a unidade mínima de alocação do disco
# O tamanho do disco deve ser múltiplo do tamanho do bloco
# =============================================================================
TAMANHO_DISCO = 128 * 1024 * 1024      # 128 MB (enunciado)
TAMANHO_BLOCO = 2048                   # 2048 Bytes (enunciado)
TOTAL_BLOCOS = TAMANHO_DISCO // TAMANHO_BLOCO # 65.536 blocos no total

# Cada bloco guarda 8 i-nodes (cada i-node ocupa 256 bytes, e cada bloco tem 2048 bytes)
# 1 bloco ocupa 2048 bytes, 65.536 blocos = 134.217.728 bytes = 128 MB
# # O bitmap precisa de 1 bit por BLOCO (não por byte)
# 1 bit é 1/8 byte, 65.536 blocos = 65.536 bits = 8.192 bytes

# =============================================================================
# LAYOUT DO DISCO  / Mapa de blocos

# Eu escolhi que a tabela ocuparia 512 blocos e cada bloco ocupa 8-inodes
# Tabela ocupa 512 blocos (6 a 517) / Cada bloco tem 2048 bytes
# Total de i-nodes = 512 blocos * 8 i-nodes por bloco = 4.096 i-nodes
# Cada i-node ocupa 256 bytes, logo cada bloco tem 8 i-nodes (2048 / 256 = 8)

# O disco lê o pacote em 8 bits (byte) -> 1 byte para guardar 4096 bits (i-nodes)
# Disco aloca em blocos inteiros de 2048 bytes
# =============================================================================

BLOCO_SUPERBLOCO = 0            # Informações gerais do FS

INICIO_BITMAP_BLOCOS = 1        # Blocos 1 a 4: Bitmap de blocos livres (65.536 bits = 8.192 bytes)
QTD_BLOCOS_BITMAP_DADOS = 4     # Quantidade de blocos usados que o bitmap de blocos ocupa 
                                # (4 blocos = 8.192 bytes = 65.536 bits = 65.536 blocos)

INICIO_BITMAP_INODES = 5        # Bloco 5 bitmap de i-nodes livres (4.096 inodes = 512 bytes)
QTD_BLOCOS_BITMAP_INODES = 1    # Quantidade de blocos usados que o bitmap de inodes ocupa 
                                # (1 bloco = 2048 bytes = 8.192 bits = 8.192 inodes)    
                                
QTD_BLOCOS_TABELA_INODES = 512 # (512 blocos * 8 i-nodes/bloco = 4.096 i-nodes)
INICIO_TABELA_INODES = 6        # 512 blocos (vai do 6 até o 517)
INICIO_BLOCOS_DADOS = 518       # O que sobra é para os dados (518 até 65535)

# =============================================================================
# ESTRUTURA DO I-NODE
# Eu escolhi que seriam 512 blocos para a tabela de i-nodes, cada bloco com 8 i-nodes
# totalizando 4.096 i-nodes.
# Cada i-node ocupa 256 bytes, logo cada bloco tem 8 i-nodes (2048 / 256 = 8)
# =============================================================================

TAMANHO_INODE = 256                                         # Tamanho fixo de cada i-node
INODES_POR_BLOCO = TAMANHO_BLOCO // TAMANHO_INODE           # 8 i-nodes por bloco
TOTAL_INODES = QTD_BLOCOS_TABELA_INODES * INODES_POR_BLOCO  # 4.096 i-nodes no total
INODE_RAIZ = 0                                              # O primeiro i-node é sempre a raiz "/"

# =============================================================================
# ESTRUTURA DE DIRETÓRIOS (ENTRADAS)
# Define como os filhos são listados dentro do bloco de dados de um diretório.
# Formato: 60 bytes de nome + 4 bytes de número do i-node.
# pro código de tipo struct tenho que consultar a documentação struct
# =============================================================================

# < indica little-endian, 60s indica string de 60 bytes, I indica inteiro de 4 bytes
FORMATO_ENTRADA_DIR = '<60sI' # Ele guarda a lista de filhos (nome + i-node) 
                              # dentro do bloco de dados do diretório
TAMANHO_ENTRADA_DIR = 64   # 60 + 4
# 4 bytes para o endereço/indice (I) tenho 4096 i-nodes para guardar o número 4096
# eu precisaria de 12 bits, poderiau usar 2 bytes (16 bits) para guardar o número do i-node
# mas os exemplos de sistema de arquivo usam mais que 4 bytes (32 bits)... NFTS usa 8 bytes por exemplo
# com 2 bytes ficaria quebraodo a tamanho das entradas... (62 bytes) 

# =============================================================================
# FORMATOS DAS STRUCTS (MÓDULO 'STRUCT')
# 64s: Nome, 32s: Criador, 32s: Dono, I: Tamanho, q: Data Criação, q: Data Mod,
# I: Permissões, 12I: 12 Ponteiros de dados, I: Ponteiro p/ outro inode (Link), 
# I: Tipo, 48s: Padding
# =============================================================================

FORMATO_INODE = '<64s32s32sIqqI12III48s' # formato do i-node (256 bytes)

# Formato do Superbloco
# I: Número Mágico, I: Total de Blocos, I: Blocos Livres, I: Total de I-nodes, I: I-nodes Livres
FORMATO_SUPERBLOCO = '<IIIII' #superbloco ocupa 20 bytes (5 campos de 4 bytes cada)
# superbloco é o identificador do sistema de arquivos, ele guarda informações gerais do FS

# =============================================================================
# FLAGS E IDENTIFICADORES
# =============================================================================

MAGIC_NUMBER = 0x12345678 # Hexadecimal... 8 digitos = 32 bits = 4 bytes (I) = 1 inteiro

# Os 3 são marcadores de tipo de arquivo, usados no campo "Tipo" do i-node
TIPO_ARQUIVO = 0          
TIPO_DIRETORIO = 1
TIPO_LINK = 2                    # Para o comando ln -s

I_NODE_INVALIDO = 0xFFFFFFFF  # Valor especial para indicar que um i-node não é válido (não alocado) 
# é o valor maior possível, valor que não tem como ser usado em um i-node

# =============================================================================
# LIMITES
# =============================================================================

PONTEIROS_DIRETOS = 12 # 48 bytes é o que tinha sobrado sem desperdiçar espaço
TAMANHO_MAX_ARQUIVO_DIRETO = PONTEIROS_DIRETOS * TAMANHO_BLOCO   # 24 KB máximo por arquivo
                                # 12 ponteiros diretos x 2048 bytes = 24 KB máximo por arquivo


# Tamanho em bytes dos campos do i-node (Total = 256 bytes)
# Nome:          64 bytes  (64s)
# Criador:       32 bytes  (32s)
# Dono:          32 bytes  (32s)
# Tamanho:        4 bytes  (I)
# Data criação:   8 bytes  (q)
# Data mod:       8 bytes  (q)
# Permissões:     4 bytes  (I)
# 12 ponteiros:  48 bytes  (12I)
# Tipo:           4 bytes  (I)  
# Próximo(Link):  4 bytes  (I)
# Padding:       48 bytes  (48s)
# TOTAL:        256 bytes
