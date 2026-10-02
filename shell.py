# shell.py
import cmd
import shlex
from fs import (
    # Funções que o shell chama. Cada uma recebe nomes/caminhos e devolve
    # i-nodes ou strings. O shell não sabe COMO elas fazem isso.
    obter_inode_raiz,      # devolve o i-node da raiz "/"
    buscar_caminho,        # resolve "/a/b/c" a partir de um diretório
    criar_arquivo,         # touch
    remover_arquivo,       # rm
    ler_arquivo,           # cat
    escrever_arquivo,      # echo > / >>
    criar_diretorio,       # mkdir
    remover_diretorio,     # rmdir
    listar_diretorio,      # ls
    copiar,                # cp
    mover,                 # mv
    criar_link_simbolico,  # ln -s
    listar_inodes_filhos,  # ls -a
)


class TerminalFS(cmd.Cmd):
    # O cmd.Cmd cuida do loop de leitura, do help automático baseado nas
    # métodos chamados 'do_<nome>' para que virem comandos do shell.
    intro = "Sistema de Arquivos ligado. Digite 'help' ou '?' para listar comandos.\n"
    prompt = "fs> "

    def __init__(self):
        # super().__init__() precisa vir antes de qualquer outra coisa
        # porque é ele que inicializa as estruturas internas do cmd.Cmd.
        super().__init__()

        # O diretório atual é sempre um objeto Inode, nunca uma string.
        # Todos os comandos que aceitam caminho relativo partem daqui.
        self.diretorio_atual = obter_inode_raiz()

    # -------------------------------------------------------------------------
    # ARQUIVOS
    # -------------------------------------------------------------------------

    def do_touch(self, arg):
        """Cria um arquivo vazio. Uso: touch <nome_arquivo>"""
        nome = arg.strip()
        if not nome:
            print("touch: faltou o nome do arquivo")
            return
        try:
            criar_arquivo(nome, self.diretorio_atual)
        except Exception as e:
            # Se não capturar, o shell quebra e o usuário perde a sessão.
            print(f"touch: {e}")

    def do_rm(self, arg):
        """Remove um arquivo. Uso: rm <nome_arquivo>"""
        nome = arg.strip()
        if not nome:
            print("rm: faltou o nome do arquivo")
            return
        try:
            remover_arquivo(nome, self.diretorio_atual)
        except Exception as e:
            print(f"rm: {e}")

    def do_cat(self, arg):
        """Lê o conteúdo de um arquivo. Uso: cat <nome_arquivo>"""
        nome = arg.strip()
        if not nome:
            print("cat: faltou o nome do arquivo")
            return
        try:
            # end="" evita que print acrescente um '\n' extra no final.
            print(ler_arquivo(nome, self.diretorio_atual), end='')
        except Exception as e:
            print(f"cat: {e}")

    def do_echo(self, arg):
        """Escreve em arquivo. Uso: echo <texto> > arquivo   ou   echo <texto> >> arquivo"""
        # shlex.split remove as aspas, então 'echo "a > b" > arq' funciona.
        tokens = shlex.split(arg)

        if '>>' in tokens:
            idx, truncar = tokens.index('>>'), False
        elif '>' in tokens:
            idx, truncar = tokens.index('>'), True
        else:
            print("echo: uso: echo <texto> > arquivo   ou   echo <texto> >> arquivo")
            return

        # Tudo antes do operador vira o texto; tudo depois vira o nome do
        # arquivo. ' '.join permite gravar 'a b c' de uma vez em vez de só 'a'.
        texto   = ' '.join(tokens[:idx])
        arquivo = ' '.join(tokens[idx+1:])

        if not arquivo:
            print("echo: faltou o nome do arquivo de destino")
            return

        try:
            # Echo sempre grava com quebra de linha no final.
            escrever_arquivo(arquivo, texto + '\n',
                             self.diretorio_atual, truncar=truncar)
        except Exception as e:
            print(f"echo: {e}")

    def do_cp(self, arg):
        """Copia arquivo. Uso: cp <origem> <destino>"""
        partes = arg.split()
        if len(partes) != 2:
            print("cp: uso: cp <origem> <destino>")
            return
        try:
            copiar(partes[0], partes[1], self.diretorio_atual)
        except Exception as e:
            print(f"cp: {e}")

    def do_mv(self, arg):
        """Move/renomeia. Uso: mv <origem> <destino>"""
        partes = arg.split()
        if len(partes) != 2:
            print("mv: uso: mv <origem> <destino>")
            return
        try:
            mover(partes[0], partes[1], self.diretorio_atual)
        except Exception as e:
            print(f"mv: {e}")

    def do_ln(self, arg):
        """Cria link simbólico. Uso: ln -s <alvo> <nome_do_link>"""
        partes = arg.split()
        if len(partes) != 3 or partes[0] != '-s':
            print("ln: uso: ln -s <alvo> <nome_do_link>")
            return
        try:
            criar_link_simbolico(partes[1], partes[2], self.diretorio_atual)
        except Exception as e:
            print(f"ln: {e}")

    # -------------------------------------------------------------------------
    # DIRETÓRIOS
    # -------------------------------------------------------------------------

    def do_ls(self, arg):
        """Lista conteúdo. Uso: ls [-a] [caminho]"""
        mostrar_tudo = False
        partes = arg.split()
        if partes and partes[0] == '-a':
            mostrar_tudo = True
            partes = partes[1:]

        nome = ' '.join(partes).strip()
        alvo = self.diretorio_atual

        if nome and nome != ".":
            try:
                alvo = buscar_caminho(nome, self.diretorio_atual)
            except Exception as e:
                print(f"ls: {e}")
                return

        try:
            if mostrar_tudo:
                # listar_inodes_filhos é a fonte crua — inclui '.' e '..'.
                itens = [f.nome for f in listar_inodes_filhos(alvo)]
            else:
                # listar_diretorio já filtra '.' e '..'.
                itens = listar_diretorio(alvo)
        except Exception as e:
            print(f"ls: {e}")
            return

        for item in itens:
            print(item)

    def do_mkdir(self, arg):
        """Cria diretório. Uso: mkdir <nome>"""
        nome = arg.strip()
        if not nome:
            print("mkdir: faltou o nome do diretório")
            return
        try:
            criar_diretorio(nome, self.diretorio_atual)
        except FileExistsError:
            print(f"mkdir: '{nome}' já existe")
        except Exception as e:
            print(f"mkdir: {e}")

    def do_rmdir(self, arg):
        """Remove diretório vazio. Uso: rmdir <nome>"""
        nome = arg.strip()
        if not nome:
            print("rmdir: faltou o nome do diretório")
            return
        try:
            # O fs é quem verifica se o diretório está vazio.
            remover_diretorio(nome, self.diretorio_atual)
        except Exception as e:
            print(f"rmdir: {e}")

    def do_cd(self, arg):
        """Troca de diretório. Uso: cd [caminho]"""
        nome = arg.strip()
        if not nome:
            return

        try:
            self.diretorio_atual = buscar_caminho(nome, self.diretorio_atual)
            print(self.diretorio_atual.caminho_completo())
        except Exception as e:
            print(f"cd: {e}")

    def do_pwd(self, arg):
        """Mostra o diretório atual."""
        print(self.diretorio_atual.caminho_completo())

    # -------------------------------------------------------------------------
    # CONTROLE
    # -------------------------------------------------------------------------

    def do_exit(self, arg):
        """Sai do shell."""
        print("Saindo do Sistema de Arquivos...")
        # Retornar True é o sinal que o cmd.Cmd entende como "quero sair".
        return True

    def do_quit(self, arg):
        """Atalho pra sair."""
        return self.do_exit(arg)


if __name__ == '__main__':
    # Só dispara o cmdloop quando o arquivo é executado diretamente.
    # Se outro arquivo fizer 'from shell import X', nada roda.
    terminal = TerminalFS()
    try:
        terminal.cmdloop()
    except KeyboardInterrupt:
        print("\nInterrupção detectada. Saindo...")