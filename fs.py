# fs.py
import struct
import time
from constantes import *


# Nome do arquivo que simula o disco rígido.
ARQUIVO_DISCO = "disk.img"


# =============================================================================
# PRIMITIVAS DE DISCO
# =============================================================================
# Lê e escreve bytes crus no arquivo do disco. Nada dealto nível chama isso diretamente 
# tudo passa pela classe Inode ou pelos bitmaps

def ler_bytes(offset, quantidade):
    """Lê 'quantidade' bytes a partir de 'offset' absoluto no disco."""
    with open(ARQUIVO_DISCO, 'rb') as f:
        f.seek(offset)
        return f.read(quantidade)


def escrever_bytes(offset, dados):
    """Escreve bytes a partir de 'offset' absoluto no disco."""
    with open(ARQUIVO_DISCO, 'r+b') as f:
        f.seek(offset)
        f.write(dados)


def ler_bloco(numero_bloco):
    """Lê um bloco inteiro (TAMANHO_BLOCO bytes)."""
    return ler_bytes(numero_bloco * TAMANHO_BLOCO, TAMANHO_BLOCO)


def escrever_bloco(numero_bloco, dados):
    """Escreve um bloco inteiro. 'dados' precisa ter exatamente TAMANHO_BLOCO bytes."""
    if len(dados) != TAMANHO_BLOCO:
        raise ValueError(f"bloco precisa ter {TAMANHO_BLOCO} bytes, tem {len(dados)}")
    escrever_bytes(numero_bloco * TAMANHO_BLOCO, dados)


# =============================================================================
# CLASSE INODE
# =============================================================================
# Aqui que tem as informações de UM arquivo, diretório ou link. Toda a lógica de
# serialização (bytes <-> objeto) e de leitura/escrita fica aqui.
# O shell só lida com objetos Inode
class Inode:
    def __init__(self, numero, nome, tipo,
                 criador="root", dono="root",
                 tamanho=0, data_criacao=None, data_modificacao=None,
                 permissoes=0b111111, ponteiros=None, proximo=0):
        self.numero          = numero
        self.nome            = nome
        self.tipo            = tipo
        self.criador         = criador
        self.dono            = dono
        self.tamanho         = tamanho
        agora                = int(time.time())
        self.data_criacao    = data_criacao if data_criacao else agora
        self.data_modificacao = data_modificacao if data_modificacao else agora
        self.permissoes      = permissoes
        # 12 ponteiros para blocos de dados. Zero = ponteiro não usado.
        self.ponteiros       = ponteiros if ponteiros else [0] * 12
        # Alvo de link simbólico. Zero quando o i-node não é um link.
        self.proximo         = proximo

    # Serialização: strings viram bytes de tamanho fixo (truncadas e
    # preenchidas com \0 até o tamanho que o FORMATO_INODE exige).

    def para_bytes(self):
        """Empacota o i-node nos 256 bytes definidos por FORMATO_INODE."""
        nome_b    = self.nome.encode('utf-8')[:64].ljust(64, b'\0')
        criador_b = self.criador.encode('utf-8')[:32].ljust(32, b'\0')
        dono_b    = self.dono.encode('utf-8')[:32].ljust(32, b'\0')
        return struct.pack(
            FORMATO_INODE,
            nome_b,
            criador_b,
            dono_b,
            self.tamanho,
            self.data_criacao,
            self.data_modificacao,
            self.permissoes,
            *self.ponteiros,     # 12 inteiros separados
            self.tipo,
            self.proximo,
            b'\0' * 48,          # padding até fechar 256 bytes
        )

    @classmethod
    def de_bytes(cls, numero, dados):
        """Desempacota 256 bytes num objeto Inode."""
        campos = struct.unpack(FORMATO_INODE, dados)
        (nome, criador, dono, tamanho, dt_cri, dt_mod, perm, *resto) = campos

        ponteiros = list(resto[:12])
        tipo      = resto[12]
        proximo   = resto[13]

        return cls(
            numero           = numero,
            nome             = nome.rstrip(b'\0').decode('utf-8'),
            tipo             = tipo,
            criador          = criador.rstrip(b'\0').decode('utf-8'),
            dono             = dono.rstrip(b'\0').decode('utf-8'),
            tamanho          = tamanho,
            data_criacao     = dt_cri,
            data_modificacao = dt_mod,
            permissoes       = perm,
            ponteiros        = ponteiros,
            proximo          = proximo,
        )

    # O offset de um i-node dentro da tabela é calculado a partir do número:
    # posição na tabela * tamanho de cada ficha.

    def _offset_no_disco(self):
        return INICIO_TABELA_INODES * TAMANHO_BLOCO + self.numero * TAMANHO_INODE

    def salvar(self):
        """Escreve este i-node no disco."""
        escrever_bytes(self._offset_no_disco(), self.para_bytes())

    @classmethod
    def carregar(cls, numero):
        """Lê um i-node do disco pelo número."""
        offset = INICIO_TABELA_INODES * TAMANHO_BLOCO + numero * TAMANHO_INODE
        dados = ler_bytes(offset, TAMANHO_INODE)
        return cls.de_bytes(numero, dados)

    def eh_raiz(self):
        return self.numero == INODE_RAIZ

    def eh_diretorio(self):
        return self.tipo == TIPO_DIRETORIO

    @property
    def pai(self):
        """Devolve o Inode do pai, lendo a entrada '..' do próprio diretório. """
        if self.eh_raiz():
            return self

        n_entradas = TAMANHO_BLOCO // TAMANHO_ENTRADA_DIR

        for bloco in self.ponteiros:
            if bloco == 0:
                break
            dados = ler_bloco(bloco)
            for i in range(n_entradas):
                off = i * TAMANHO_ENTRADA_DIR
                nome_b, num = struct.unpack(
                    FORMATO_ENTRADA_DIR,
                    dados[off:off+TAMANHO_ENTRADA_DIR]
                )
                if num == I_NODE_INVALIDO:
                    break
                if nome_b.rstrip(b'\0') == b'..':
                    return Inode.carregar(num)

        raise OSError(f"diretório '{self.nome}' não tem entrada '..'")

    def caminho_completo(self):
        """Monta o caminho tipo '/a/b/c' subindo pelos pais."""
        if self.eh_raiz():
            return "/"

        partes = [self.nome]
        atual = self
        while not atual.eh_raiz():
            atual = atual.pai
            if atual.eh_raiz():
                break
            partes.append(atual.nome)

        return "/" + "/".join(reversed(partes))


# =============================================================================
# BITMAPS
# =============================================================================
# O bitmap é uma sequência de bits: 0 = livre, 1 = ocupado. São duas
# instâncias independentes: uma para blocos, outra para i-nodes. Cada
# alocação/liberação faz o ciclo ler -> modificar bit -> escrever.

def _testar_bit(dados, indice):
    """Retorna 0 ou 1 do bit na posição 'indice'."""
    byte_i = indice // 8
    bit_i  = indice % 8
    return (dados[byte_i] >> bit_i) & 1


def _setar_bit(dados, indice, valor):
    """Devolve novos bytes com o bit setado/limpo."""
    byte_i = indice // 8
    bit_i  = indice % 8
    b = bytearray(dados)
    if valor:
        b[byte_i] |= (1 << bit_i)
    else:
        b[byte_i] &= ~(1 << bit_i)
    return bytes(b)


def _ler_bitmap_blocos():
    return ler_bytes(INICIO_BITMAP_BLOCOS * TAMANHO_BLOCO,
                     QTD_BLOCOS_BITMAP_DADOS * TAMANHO_BLOCO)


def _escrever_bitmap_blocos(dados):
    escrever_bytes(INICIO_BITMAP_BLOCOS * TAMANHO_BLOCO, dados)


def alocar_bloco():
    """Acha o primeiro bloco livre, marca como ocupado, devolve o número."""
    dados = _ler_bitmap_blocos()
    for i in range(TOTAL_BLOCOS):
        if _testar_bit(dados, i) == 0:
            dados = _setar_bit(dados, i, 1)
            _escrever_bitmap_blocos(dados)
            return i
    raise OSError("disco cheio: sem blocos livres")


def liberar_bloco(numero_bloco):
    dados = _ler_bitmap_blocos()
    dados = _setar_bit(dados, numero_bloco, 0)
    _escrever_bitmap_blocos(dados)


def _ler_bitmap_inodes():
    return ler_bytes(INICIO_BITMAP_INODES * TAMANHO_BLOCO,
                     QTD_BLOCOS_BITMAP_INODES * TAMANHO_BLOCO)


def _escrever_bitmap_inodes(dados):
    escrever_bytes(INICIO_BITMAP_INODES * TAMANHO_BLOCO, dados)


def alocar_inode():
    """Acha o primeiro i-node livre, marca como ocupado, devolve o número."""
    dados = _ler_bitmap_inodes()
    for i in range(TOTAL_INODES):
        if _testar_bit(dados, i) == 0:
            dados = _setar_bit(dados, i, 1)
            _escrever_bitmap_inodes(dados)
            return i
    raise OSError("sem i-nodes livres")


def liberar_inode(numero_inode):
    dados = _ler_bitmap_inodes()
    dados = _setar_bit(dados, numero_inode, 0)
    _escrever_bitmap_inodes(dados)


# =============================================================================
# NAVEGAÇÃO E LISTAGEM
# =============================================================================
# Um diretório guarda sua lista de filhos em blocos de dados. Cada entrada
# tem 64 bytes (60 de nome + 4 de número do i-node). Cabe 32 entradas por
# bloco. A sentinela I_NODE_INVALIDO marca o fim da lista.

def obter_inode_raiz():
    return Inode.carregar(INODE_RAIZ)


def listar_inodes_filhos(diretorio):
    """Devolve a lista de i-nodes filhos deste diretório.

    O nome de cada filho é sobrescrito pelo nome que está na entrada do
    diretório. Isso é o que faz '.' e '..' aparecerem com o nome certo,
    mesmo quando apontam para i-nodes que têm outro nome.
    """
    if diretorio.tipo != TIPO_DIRETORIO:
        raise OSError(f"'{diretorio.nome}' não é um diretório")

    filhos = []
    n_entradas = TAMANHO_BLOCO // TAMANHO_ENTRADA_DIR

    for bloco in diretorio.ponteiros:
        if bloco == 0:
            break
        dados = ler_bloco(bloco)
        for i in range(n_entradas):
            off = i * TAMANHO_ENTRADA_DIR
            nome_b, num = struct.unpack(
                FORMATO_ENTRADA_DIR,
                dados[off:off+TAMANHO_ENTRADA_DIR]
            )
            if num == I_NODE_INVALIDO:
                return filhos

            nome = nome_b.rstrip(b'\0').decode('utf-8')
            filho = Inode.carregar(num)
            filho.nome = nome
            filhos.append(filho)
    return filhos


def listar_diretorio(diretorio):
    """Devolve os NOMES dos filhos, escondendo '.' e '..' (como o ls do Unix)."""
    return [f.nome for f in listar_inodes_filhos(diretorio)
            if f.nome not in ('.', '..')]


def buscar_filho(diretorio, nome):
    """Procura um filho pelo nome dentro do diretório."""
    for f in listar_inodes_filhos(diretorio):
        if f.nome == nome:
            return f
    raise FileNotFoundError(f"'{nome}' não encontrado em '{diretorio.nome}'")


def buscar_caminho(caminho, atual):
    """Resolve '/a/b/c' ou 'a/b' a partir de 'atual'."""
    if caminho.startswith("/"):
        no = obter_inode_raiz()
        partes = [p for p in caminho.split("/") if p]
    else:
        no = atual
        partes = [p for p in caminho.split("/") if p]

    for parte in partes:
        no = buscar_filho(no, parte)
    return no


def adicionar_filho(pai, num_filho, nome):
    """Insere uma entrada (nome + número) na lista de filhos de 'pai'.

    Blocos novos nascem com todas as entradas preenchidas com sentinela,
    para que a busca por slot vago funcione nas próximas inserções.
    """
    nome_b = nome.encode('utf-8')[:60].ljust(60, b'\0')

    for i, bloco in enumerate(pai.ponteiros):
        if bloco == 0:
            novo = alocar_bloco()
            pai.ponteiros[i] = novo

            buf = bytearray(TAMANHO_BLOCO)
            n_entradas = TAMANHO_BLOCO // TAMANHO_ENTRADA_DIR
            for k in range(n_entradas):
                off_num = k * TAMANHO_ENTRADA_DIR + 60
                buf[off_num:off_num+4] = struct.pack('<I', I_NODE_INVALIDO)

            buf[0:60]   = nome_b
            buf[60:64]  = struct.pack('<I', num_filho)

            escrever_bloco(novo, bytes(buf))
            pai.tamanho += TAMANHO_ENTRADA_DIR
            pai.salvar()
            return

        dados = bytearray(ler_bloco(bloco))
        n_entradas = TAMANHO_BLOCO // TAMANHO_ENTRADA_DIR
        for j in range(n_entradas):
            off = j * TAMANHO_ENTRADA_DIR
            num = struct.unpack('<I', bytes(dados[off+60:off+64]))[0]
            if num == I_NODE_INVALIDO:
                dados[off:off+60]     = nome_b
                dados[off+60:off+64]  = struct.pack('<I', num_filho)
                escrever_bloco(bloco, bytes(dados))
                pai.tamanho += TAMANHO_ENTRADA_DIR
                pai.salvar()
                return

    raise OSError("diretório cheio (limite de 12 blocos)")


# =============================================================================
# OPERAÇÕES DE CRIAÇÃO
# =============================================================================

def criar_arquivo(nome, pai):
    """touch: cria um arquivo vazio no diretório 'pai'."""
    if not nome or "/" in nome:
        raise ValueError(f"nome inválido: {nome!r}")

    for f in listar_inodes_filhos(pai):
        if f.nome == nome:
            raise FileExistsError(nome)

    num = alocar_inode()

    novo = Inode(
        numero    = num,
        nome      = nome,
        tipo      = TIPO_ARQUIVO,
        tamanho   = 0,
        ponteiros = [0] * 12,
        proximo   = 0,
    )

    novo.salvar()
    adicionar_filho(pai, num, nome)


def criar_diretorio(nome, pai):
    """mkdir: cria 1 i-node + 1 bloco com ['.', '..'] + sentinelas."""
    if not nome or "/" in nome:
        raise ValueError(f"nome inválido: {nome!r}")

    for f in listar_inodes_filhos(pai):
        if f.nome == nome:
            raise FileExistsError(nome)

    num_dir = alocar_inode()
    bloco   = alocar_bloco()

    novo_dir = Inode(
        numero    = num_dir,
        nome      = nome,
        tipo      = TIPO_DIRETORIO,
        tamanho   = 2 * TAMANHO_ENTRADA_DIR,
        ponteiros = [bloco] + [0] * 11,
        proximo   = 0,
    )
    novo_dir.salvar()

    buf = bytearray(TAMANHO_BLOCO)
    n_entradas = TAMANHO_BLOCO // TAMANHO_ENTRADA_DIR

    # Pre preenche todas as entradas com sentinela
    for k in range(n_entradas):
        off_num = k * TAMANHO_ENTRADA_DIR + 60
        buf[off_num:off_num+4] = struct.pack('<I', I_NODE_INVALIDO)

    # Entrada 0: "." aponta para o próprio diretório
    buf[0:60]    = b'.' + b'\0' * 59
    buf[60:64]   = struct.pack('<I', num_dir)

    # Entrada 1: ".." aponta para o pai
    buf[64:124]  = b'..' + b'\0' * 58
    buf[124:128] = struct.pack('<I', pai.numero)

    escrever_bloco(bloco, bytes(buf))
    adicionar_filho(pai, num_dir, nome)


# =============================================================================
# LEITURA E ESCRITA DE ARQUIVOS
# =============================================================================

def ler_arquivo(nome, pai):
    """cat: devolve o conteúdo do arquivo como string. Segue links."""
    arq = buscar_filho(pai, nome)

    if arq.tipo == TIPO_LINK:
        arq = _resolver_link(arq)

    if arq.tipo != TIPO_ARQUIVO:
        raise OSError(f"'{nome}' não é um arquivo comum")

    if arq.tamanho == 0:
        return ""

    n_blocos = (arq.tamanho + TAMANHO_BLOCO - 1) // TAMANHO_BLOCO

    pedacos = []
    for i in range(n_blocos):
        bloco = arq.ponteiros[i]
        if bloco == 0:
            raise OSError(f"i-node do '{nome}' aponta pra bloco vazio")
        pedacos.append(ler_bloco(bloco))

    dados = b''.join(pedacos)

    # Corta no tamanho real: o último bloco tem padding de zeros.
    return dados[:arq.tamanho].decode('utf-8')


def escrever_arquivo(nome, conteudo, pai, truncar=True):
    """Escreve conteúdo em um arquivo. Cria se não existir. Segue links.

    truncar=True (>) apaga o conteúdo antigo antes de escrever.
    truncar=False (>>) concatena ao conteúdo que já existe.

    Toda validação (tamanho máximo, tipo do i-node) acontece ANTES de
    liberar qualquer bloco antigo — para não perder dados se a escrita
    for rejeitada no meio do caminho.
    """
    try:
        arq = buscar_filho(pai, nome)
    except FileNotFoundError:
        criar_arquivo(nome, pai)
        arq = buscar_filho(pai, nome)

    if arq.tipo == TIPO_LINK:
        arq = _resolver_link(arq)

    if arq.tipo != TIPO_ARQUIVO:
        raise OSError(f"'{nome}' não é um arquivo comum")

    if not truncar:
        conteudo = ler_arquivo(nome, pai) + conteudo

    dados = conteudo.encode('utf-8')

    n_blocos_necessarios = (len(dados) + TAMANHO_BLOCO - 1) // TAMANHO_BLOCO
    if n_blocos_necessarios > PONTEIROS_DIRETOS:
        raise OSError(f"arquivo grande demais ({len(dados)} bytes, "
                      f"máx {TAMANHO_MAX_ARQUIVO_DIRETO})")

    if truncar:
        for p in arq.ponteiros:
            if p != 0:
                liberar_bloco(p)
        arq.ponteiros = [0] * 12

    for i in range(n_blocos_necessarios):
        inicio = i * TAMANHO_BLOCO
        fim    = inicio + TAMANHO_BLOCO
        pedaco = dados[inicio:fim]

        pedaco = pedaco.ljust(TAMANHO_BLOCO, b'\0')

        if arq.ponteiros[i] == 0:
            arq.ponteiros[i] = alocar_bloco()

        escrever_bloco(arq.ponteiros[i], pedaco)

    arq.tamanho          = len(dados)
    arq.data_modificacao = int(time.time())
    arq.salvar()


# =============================================================================
# REMOÇÃO
# =============================================================================

def _remover_entrada(pai, num_alvo):
    """Remove a entrada que aponta pra num_alvo, compactando o bloco.

    A compactação move o último filho da lista para a posição vaga e
    reduz o tamanho. Assim a lista nunca tem buracos no meio.
    """
    n_entradas = TAMANHO_BLOCO // TAMANHO_ENTRADA_DIR

    for bloco in pai.ponteiros:
        if bloco == 0:
            break

        dados = bytearray(ler_bloco(bloco))

        entradas = []
        for i in range(n_entradas):
            off = i * TAMANHO_ENTRADA_DIR
            nome_b, num = struct.unpack(
                FORMATO_ENTRADA_DIR,
                bytes(dados[off:off+TAMANHO_ENTRADA_DIR])
            )
            if num == I_NODE_INVALIDO:
                break
            entradas.append((nome_b, num))

        idx_alvo = None
        for i, (_, num) in enumerate(entradas):
            if num == num_alvo:
                idx_alvo = i
                break

        if idx_alvo is None:
            continue

        entradas[idx_alvo] = entradas[-1]
        entradas.pop()

        buf = bytearray(TAMANHO_BLOCO)
        for i in range(n_entradas):
            off = i * TAMANHO_ENTRADA_DIR + 60
            buf[off:off+4] = struct.pack('<I', I_NODE_INVALIDO)

        for i, (nome_b, num) in enumerate(entradas):
            off = i * TAMANHO_ENTRADA_DIR
            buf[off:off+60]    = nome_b
            buf[off+60:off+64] = struct.pack('<I', num)

        escrever_bloco(bloco, bytes(buf))
        pai.tamanho -= TAMANHO_ENTRADA_DIR
        pai.salvar()
        return

    raise OSError(f"entrada {num_alvo} não encontrada no diretório pai")


def remover_arquivo(nome, pai):
    """rm: remove um arquivo comum e libera seus recursos."""
    alvo = buscar_filho(pai, nome)

    if alvo.tipo != TIPO_ARQUIVO:
        raise OSError(f"'{nome}' não é um arquivo comum")

    for p in alvo.ponteiros:
        if p != 0:
            liberar_bloco(p)

    liberar_inode(alvo.numero)
    _remover_entrada(pai, alvo.numero)


def remover_diretorio(nome, pai):
    """rmdir: remove diretório vazio (só com '.' e '..')."""
    alvo = buscar_filho(pai, nome)

    if alvo.tipo != TIPO_DIRETORIO:
        raise OSError(f"'{nome}' não é um diretório")

    if alvo.eh_raiz():
        raise OSError("não é possível remover a raiz")

    # Diretório vazio = apenas '.' e '..' = 2 entradas de 64 bytes.
    if alvo.tamanho != 2 * TAMANHO_ENTRADA_DIR:
        raise OSError(f"diretório '{nome}' não está vazio")

    for p in alvo.ponteiros:
        if p != 0:
            liberar_bloco(p)

    liberar_inode(alvo.numero)
    _remover_entrada(pai, alvo.numero)


# =============================================================================
# CÓPIA E MOVIMENTAÇÃO
# =============================================================================

def copiar(origem, destino, pai):
    """cp: copia arquivo origem pra arquivo destino. Segue links na origem."""
    arq_origem = buscar_filho(pai, origem)

    if arq_origem.tipo == TIPO_LINK:
        arq_origem = _resolver_link(arq_origem)

    if arq_origem.tipo != TIPO_ARQUIVO:
        raise OSError(f"'{origem}' não é um arquivo comum")

    try:
        buscar_filho(pai, destino)
        raise FileExistsError(f"'{destino}' já existe")
    except FileNotFoundError:
        pass

    conteudo = ler_arquivo(origem, pai)
    criar_arquivo(destino, pai)
    escrever_arquivo(destino, conteudo, pai)


def _renomear_entrada(pai, num_alvo, novo_nome):
    """Atualiza só o campo nome da entrada que aponta pra num_alvo."""
    n_entradas = TAMANHO_BLOCO // TAMANHO_ENTRADA_DIR
    nome_b = novo_nome.encode('utf-8')[:60].ljust(60, b'\0')

    for bloco in pai.ponteiros:
        if bloco == 0:
            break

        dados = bytearray(ler_bloco(bloco))
        for i in range(n_entradas):
            off = i * TAMANHO_ENTRADA_DIR
            num = struct.unpack('<I', bytes(dados[off+60:off+64]))[0]
            if num == I_NODE_INVALIDO:
                break
            if num == num_alvo:
                dados[off:off+60] = nome_b
                escrever_bloco(bloco, bytes(dados))
                return

    raise OSError(f"entrada {num_alvo} não encontrada no pai")


def mover(origem, destino, pai):
    """mv: renomeia arquivo ou diretório dentro do mesmo diretório.

    Atualiza o nome em DOIS lugares: no i-node (nome principal) e na
    entrada do diretório-pai (nome visível na listagem).
    """
    alvo = buscar_filho(pai, origem)

    try:
        buscar_filho(pai, destino)
        raise FileExistsError(f"'{destino}' já existe")
    except FileNotFoundError:
        pass

    alvo.nome = destino
    alvo.data_modificacao = int(time.time())
    alvo.salvar()

    _renomear_entrada(pai, alvo.numero, destino)


# =============================================================================
# LINKS SIMBÓLICOS
# =============================================================================

def _resolver_link(inode):
    """Segue o campo 'proximo' enquanto o i-node for link simbólico."""
    visto = set()
    atual = inode
    while atual.tipo == TIPO_LINK:
        if atual.numero in visto:
            raise OSError("loop de links simbólicos")
        visto.add(atual.numero)
        atual = Inode.carregar(atual.proximo)
    return atual


def criar_link_simbolico(alvo_nome, link_nome, pai):
    """ln -s: cria um i-node de link que aponta pro alvo.

    O i-node do link guarda o número do i-node alvo no campo 'proximo',
    e não usa ponteiros de bloco.
    """
    alvo = buscar_filho(pai, alvo_nome)

    try:
        buscar_filho(pai, link_nome)
        raise FileExistsError(f"'{link_nome}' já existe")
    except FileNotFoundError:
        pass

    num_link = alocar_inode()

    link = Inode(
        numero    = num_link,
        nome      = link_nome,
        tipo      = TIPO_LINK,
        tamanho   = 0,
        ponteiros = [0] * 12,
        proximo   = alvo.numero,
    )
    link.salvar()

    adicionar_filho(pai, num_link, link_nome)