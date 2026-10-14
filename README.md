# ClipLink Desktop — beta 0.4.5

Consulte o [changelog](CHANGELOG.md) para ver as mudanças desta versão.

Aplicativo local para Windows, com interface desktop, análise de link, seleção de qualidade e downloads para uma pasta escolhida. Usa `yt-dlp` para sites compatíveis; o ClipLink não promete que todos os links funcionem.

## Gerar o aplicativo `.exe` no Windows

O projeto contém um script de build que cria o executável de um único arquivo:

1. Instale Python 3.10 ou superior no Windows.
2. Extraia o ZIP com **Extrair tudo** e abra o PowerShell dentro da pasta extraída.
3. Execute o `build_windows.bat` com dois cliques, ou rode no PowerShell:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\build_windows.ps1
   ```

O arquivo será criado em `dist\ClipLink.exe`. O script instala as dependências dentro de `.build-env` e baixa os pacotes Python necessários.

O checksum SHA-256 do executável fica em `dist\ClipLink.exe.sha256` para validação após a cópia ou distribuição.

Para atualizar a distribuição, execute `package_release.ps1` com o PowerShell. O resultado sempre ficará em `release\ClipLink`, usando a mesma pasta e o mesmo executável.

Para instalar uma cópia portátil dentro desta pasta, execute `install_local.ps1`. O programa será copiado para `ClipLink-Instalado`; depois, execute `ClipLink.exe` ou `Criar_Atalho.vbs` nessa pasta.

O instalador executável oficial está em `ClipLink-Setup.exe`, na raiz desta pasta. Cada novo build sobrescreve esse mesmo arquivo e o checksum `ClipLink-Setup.exe.sha256`; não são criadas cópias versionadas. Ele reaproveita a instalação registrada, atualiza o mesmo `ClipLink.exe`, cria/atualiza os atalhos da Área de Trabalho, Menu Iniciar e barra de tarefas e registra a desinstalação do usuário; o arquivo `Uninstall-ClipLink.ps1` também fica instalado como fallback.

Para gerar novamente esse instalador, execute `build_installer.ps1` depois do build da aplicação.

Também existe um instalador MSI nativo baseado no WiX Toolset (schema v4, ferramenta local 6.0.2). Execute `build_msi.ps1` depois de `build_windows.ps1` e `package_release.ps1`. Ele usa instalação por usuário em `LocalAppData\Programs\ClipLink`, `UpgradeCode` estável e `MajorUpgrade`, permitindo que a próxima versão substitua a anterior na mesma instalação. O WiX é instalado apenas dentro de `.build-env\wix`; nenhum arquivo de build é criado fora desta pasta do projeto.

O painel `Aplicações / Atualizações` dentro do ClipLink segue o mesmo conceito de um gerenciador de aplicativos: mostra a versão instalada, consulta o manifesto HTTPS padrão do repositório GitHub do projeto e baixa o `ClipLink-Setup.exe` da nova versão. Para publicar outra versão, crie um Release no GitHub com o arquivo `ClipLink-Setup.exe` e atualize `update-manifest.json` com a versão, a URL do Release e o SHA-256 do instalador. O instalador é executado sobre a pasta atual, aguarda o EXE antigo fechar, preserva o caminho dos atalhos e reabre o mesmo ClipLink depois da atualização. Em instalações especiais, `CLIPLINK_UPDATE_URL` ainda pode substituir o canal padrão.

Para testar antes de gerar o `.exe`, dê dois cliques em `start_windows.bat`. Ele prepara o ambiente Python local, instala a versão homologada do motor `yt-dlp` e abre a interface desktop usando `pythonw.exe`. A janela do terminal fecha assim que o aplicativo é iniciado. A instalação precisa de internet; se ela falhar mas já houver um motor instalado, o app inicia com a versão existente.

O build deve ser executado em um computador Windows usando o script acima. O script valida o Python, cria um ambiente isolado e instala o PyInstaller automaticamente.

## Abrir pelo ícone, sem janela do CMD

1. Extraia o pacote completo para uma pasta fixa no computador, por exemplo `Documentos\ClipLink`.
2. Dê dois cliques em `Criar_Atalho.vbs`. Ele cria o atalho **ClipLink** na área de trabalho com o ícone do aplicativo.
3. Abra o ClipLink pelo novo ícone. A preparação e a abertura ocorrem sem deixar uma janela do CMD aberta; o processo Python também roda sem janela de terminal.

Na primeira abertura, o ClipLink prepara o ambiente local e instala o motor de download, o que exige conexão à internet e pode levar alguns minutos. Mantenha a pasta extraída no mesmo local depois de criar o atalho. Se a preparação falhar, o ClipLink mostra o caminho do registro em `%LOCALAPPDATA%\ClipLink\launcher.log`. Para ver os detalhes diretamente, execute `start_windows.bat`.

O ícone da janela e da barra de tarefas usa a identidade do ClipLink. Se preferir gerar o `.exe`, ele também abre sem CMD e recebe o mesmo ícone pelo script de build.

Na instalacao no D:, os dados de execucao, historico, relatorios, logs, downloads padrao e atualizacoes ficam na pasta `data` ao lado de `ClipLink.exe`.

## FFmpeg e Node.js

- FFmpeg é necessário para alguns links que combinam vídeo e áudio separados e para converter para MP3. Coloque `ffmpeg.exe` e, se disponível, `ffprobe.exe` em `tools/` antes do build para incluí-los no executável.
- O suporte completo ao YouTube e alguns outros extratores requer `yt-dlp-ejs` e um runtime JavaScript. O build instala `yt-dlp-ejs` junto com `yt-dlp`. Coloque `node.exe` 22 ou mais recente em `tools/` antes do build para incluí-lo; sem runtime, alguns links podem não funcionar.
- A versão compilada do `.exe` recebe o motor atualizado no build. Para incorporar correções recentes, execute novamente `build_windows.bat`, `package_release.ps1` e o instalador; a instalação existente será atualizada no mesmo caminho.
- A compatibilidade depende de cada site e pode falhar mesmo com o motor atualizado se a plataforma mudar o formato de entrega ou bloquear a solicitação. Nesse caso, tente de novo mais tarde ou use um link público diferente.
- O ClipLink avisa quando MP3 está selecionado sem FFmpeg.

Os binários de FFmpeg e Node.js não são redistribuídos neste projeto; obtenha-os de distribuidores confiáveis e observe as licenças aplicáveis.

## Recursos

- Interface desktop escura com acentos verdes, janela rolável e ícone próprio em múltiplos tamanhos.
- Campo para colar o link, análise de título, site, duração e resolução estimada.
- Saída em MP4, MP3 ou imagem original, com identificação automática de imagens e stories públicos.
- Modo Laboratório para testar links reais, salvar relatório técnico local e registrar imagens/vídeos de evidência com hash SHA-256.
- Escolha da pasta de destino, barra de progresso, cancelamento, abertura rápida do último vídeo e histórico local dos oito arquivos recentes.
- O processamento ocorre localmente; não há conta ou login de rede social. O histórico guarda somente título, plataforma e caminho do arquivo neste computador.
- Links HTTP/HTTPS públicos; URLs locais e portas fora do padrão são recusadas.
- Sem playlists. Transmissões públicas ao vivo compatíveis são permitidas. O ClipLink não bloqueia previamente um link marcado como privado ou pago, mas também não contorna login, assinatura ou DRM; o site decide se o acesso autorizado pode ser concluído.

## Escopo de uso

Use somente para conteúdo que você criou ou tem autorização para salvar. O suporte a sites adultos se limita a material público, legal, consensual e destinado a pessoas com 18 anos ou mais. O ClipLink não tenta contornar login, assinatura, DRM ou restrições de acesso.

## Rodar a partir do código no Windows

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade -r requirements-desktop.txt
python desktop_app.py
```

## Testes de regressão

Com o ambiente virtual ativado, execute:

```powershell
python -m unittest discover -s tests -v
```

Os testes cobrem a validação de URLs públicas, normalização de metadados, histórico local, seletores de qualidade, mensagens de erro e limpeza de arquivos parciais.

