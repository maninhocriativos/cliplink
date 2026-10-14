# Changelog

## 0.4.8

- O botão da área Aplicações / Atualizações agora consulta o canal e instala automaticamente a versão mais recente sobre a instalação atual.
- A atualização mantém a pasta do D e reabre o mesmo executável após concluir.

## 0.4.7

- Pasta de destino escolhida pelo usuário salva e reutilizada entre as aberturas.
- Seletor de qualidade ampliado e ajustado às resoluções encontradas no vídeo.
- Suporte de interface e runtime reforçado para YouTube, TikTok e Instagram.
- FFmpeg e Node.js incluídos no pacote Windows para melhorar formatos de alta resolução e compatibilidade.

- Dados de execucao, historico, relatorios, logs, downloads padrao e atualizacoes ficam na pasta `data` ao lado do executavel instalado no D:.
- Caches de build do Python, PyInstaller, pip, NuGet e WiX ficam no projeto no D:.

## 0.4.6 — 14/10/2026

- Ativada a rota móvel/API suportada pelo `yt-dlp` para o TikTok, com fallback automático para a rota web.
- O identificador temporário usado nessa rota não contém nem armazena credenciais, cookies ou contas.
- Instalador atualizado para reaproveitar a instalação existente e regravar atalhos da Área de Trabalho, Menu Iniciar e barra de tarefas no mesmo `ClipLink.exe`.
- Versão centralizada em um único arquivo para evitar que instalador, executável e documentação saiam divergentes.

## 0.4.5 — 13/10/2026

- Evidências baixadas no Modo Laboratório agora são anexadas ao relatório local.
- Cada imagem ou vídeo recebe caminho, tamanho, data e hash SHA-256 para comprovação de integridade.

## 0.4.4 — 13/10/2026

- Adicionado Modo Laboratório para análise de links reais.
- Relatórios locais mostram disponibilidade, formatos, codecs, resolução, tamanho estimado e motivo de falhas.
- Nenhuma credencial, cookie ou senha é coletada ou armazenada pelo modo Laboratório.

## 0.4.3 — 13/10/2026

- Removido o bloqueio preventivo baseado no campo de disponibilidade privada/paga informado pelo site.
- O usuário pode tentar um link ao qual já tenha acesso autorizado; o ClipLink não coleta credenciais nem contorna login, assinatura ou DRM.

## 0.4.2 — 13/10/2026

- Removido o limite artificial de 1 GB por arquivo.
- Permitidas transmissões públicas ao vivo compatíveis.
- Aumentadas as tentativas de rede para reduzir falhas temporárias.
- Adicionado registro de inicialização em `%LOCALAPPDATA%\ClipLink\startup.log` quando o executável não consegue carregar a interface.
- Mantidos os bloqueios de DRM, login, conteúdo privado e assinatura.

## 0.4.1 — 13/10/2026

- Interface atualizada para mostrar suporte a vídeos, stories e imagens.
- Tipo de conteúdo identificado após a análise do link.
- Formato ```Imagem``` e orientação sobre preservação da extensão original visíveis na tela.

## 0.4.0 — 13/10/2026

- Atualização do mesmo ClipLink.exe, sem criar um aplicativo separado.
- Suporte a imagens na extensão original e identificação automática de links de imagem.
- Suporte a stories públicos compatíveis com o motor yt-dlp.
- Novo modo de formato `Imagem` na tela de download.

## 0.3.0 — 13/10/2026

- Reforçada a validação de URLs HTTP/HTTPS públicas.
- Rejeitados caracteres de controle em links colados.
- Durações inválidas agora são tratadas como indisponíveis.
- Arquivos `.part` e `.ytdl` da tentativa atual são limpos após falhas ou cancelamentos.
- O caminho final do download é confinado à pasta escolhida pelo usuário.
- Build Windows compatível com `py`, `python` ou um `.venv` existente.
- Build exige Python 3.10+ e usa PyInstaller 6.22.3.
- Dependências de runtime limitadas à faixa suportada e sem pré-lançamentos no fluxo normal.
- `yt-dlp` fixado na versão homologada 2026.8.19 para builds reproduzíveis.
- Suíte de regressão ampliada para 18 testes.
- Executável Windows gerado em `dist/ClipLink.exe`.
- Script `package_release.ps1` adicionado para montar uma distribuição limpa com checksum.
- Instalador tradicional `installer/ClipLink-Setup.exe` adicionado, com escolha de pasta, atalhos e desinstalação.

### Limitações conhecidas

- FFmpeg ainda precisa ser colocado em `tools/ffmpeg.exe` para habilitar MP3 e algumas combinações de áudio/vídeo.
- Node.js 22+ em `tools/node.exe` melhora a compatibilidade com alguns extratores.
- O executável ainda não possui assinatura digital de código.
