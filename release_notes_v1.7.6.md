# Stems Organizer PRO v1.7.6 (Hotfix)

- **Correção de UI:** Removida a animação experimental de *Fade In* que estava causando bugs de renderização visual no motor do CustomTkinter (ex: tela branca na metade de baixo do programa, cores estouradas na Titlebar, ausência de bordas corrompidas).
- **Correção de Atualizador (DLL):** Removido o UPX packer para sanar o erro `Failed to load python314.dll` que corrompia a instalação automática rodando em segundo plano e incluída a flag `shellexec` para melhor lidar com as permissões da transição do Instalador para o App.
