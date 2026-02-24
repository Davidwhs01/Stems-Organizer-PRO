# O que há de novo na v1.7.2

- **Revisão Interativa**: A tela de Revisão ("Human-in-the-Loop") agora organiza visualmente os arquivos como se fossem "pastas" nativas do Windows no lugar de uma simples lista. Ela também conta com "Real-Time Move": alterar a categoria da track no dropdown faz a respectiva música voar em tempo real para sua nova pasta destino.
- **Detecção de Silêncio Aprimorada**: Modificamos o algoritmo do FFmpeg para atuar de `-91dB` para `-70dB`. Isso ignora oficialmente as trilhas fantasmas com chiado analógico mínimo (plugins na DAW). 
- **Limpador de Prefixos Ultra**: O app agora limpa agressivamente lixos de sufixos/tags de produtores desorganizados, por exemplo: `[120BPM] Kick` e `01 - Snare`, resultando em categorias idênticas.
- **Integração de Settings UI**: A aba de Configuração (API) agora é 100% nativa em vez de ficar como um Pop-Up chato em cima da sua tela.
- **Cancelador de Pastas Rápido**: Adicionado um útil botão vermelho ✖ na hora de selecionar as pastas caso o usuário escolha o diretório errado (reboot instantâneo do state sem fechar o app).
