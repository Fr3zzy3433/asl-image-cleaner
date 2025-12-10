=======================================================================================
IMAGE CLEANER ASL
=======================================================================================

Ferramenta corporativa desenvolvida por Logan Barcelos para automatizar, padronizar e acelerar a organização e limpeza das pastas de imagens utilizadas no fluxo operacional do PrintOnDemand. O sistema foi projetado para eliminar por completo o processo manual que anteriormente consumia horas de trabalho e exigia um analista dedicado integralmente à tarefa.

No cenário anterior, a limpeza das pastas do PrintOnDemand era totalmente manual e operacionalmente ineficiente. O procedimento envolvia a conferência individual de cada diretório, validação de datas, avaliação de espaço ocupado e exclusão pasta por pasta — uma atividade cansativa, suscetível a falhas e que frequentemente demandava um dia inteiro de um profissional.

Com o Image Cleaner ASL, esse fluxo foi totalmente transformado. A rotina de limpeza passou a ser automatizada, consistente e surpreendentemente rápida, executada em poucos minutos, acompanhada de logs completos e com total segurança no tratamento dos dados. O que antes era um gargalo operacional tornou-se um processo inteligente, confiável e escalável.

=======================================================================================
VISÃO GERAL
=======================================================================================

O Image Cleaner ASL é um utilitário profissional projetado para automatizar a varredura de diretórios, identificar pastas de imagens seguindo o padrão do PrintOnDemand, calcular o espaço total utilizado e executar a limpeza segura de arquivos obsoletos. O sistema combina uma interface gráfica moderna, banco de dados local totalmente automático e foco absoluto em eficiência operacional.

Funcionalidades

1. Limpeza Inteligente de Pastas
O mecanismo principal analisa diretórios, reconhecendo automaticamente estruturas válidas e inválidas. Entre os recursos estão:
• Suporte ao padrão de nomeação YYYYDDMM HHmm
• Validação automática de pastas inconsistentes
• Cálculo do espaço total antes e após a limpeza
• Exclusão segura, controlada e auditável
• Caminhos totalmente configuráveis

2. Banco SQLite Automático
Ao iniciar o software pela primeira vez, o banco local é criado dinamicamente. Ele armazena apenas configurações internas, não contém dados sensíveis e não é enviado ao GitHub ou ao instalador. Tudo ocorre sem necessidade de intervenção manual.

3. Logs Detalhados e Estruturados
Todas as ações executadas pelo sistema são registradas automaticamente. Os logs são organizados por categorias, possuem histórico contínuo e permitem auditoria completa.

4. Interface Gráfica Moderna (PySide6)
A GUI foi desenvolvida para ser simples e elegante, oferecendo navegação intuitiva e acompanhamento visual de operações prolongadas. Mesmo usuários sem experiência técnica conseguem operar com facilidade.

Tecnologias Utilizadas

Python 3.x
PySide6 (Interface gráfica)
SQLite (Banco local automático)
OS, Regex (Varredura e validação interna)
PyInstaller (Geração do executável)
Inno Setup (Criação do instalador)

Estrutura Recomendada do Repositório

ASL_ImageCleaner/
├── CLEANER.py — Código principal
├── asl.ico — Ícone da aplicação
├── script.iss — Script do instalador (Inno Setup)
├── README.md — Documentação
└── .gitignore — Ignora dist/, build/, db3 e logs

Os arquivos gerados automaticamente pelo sistema (como .db3, logs ou executáveis) não devem ser incluídos no repositório.

Instalação e Execução

Modo Desenvolvimento
python CLEANER.py

Gerar Executável
pyinstaller --onefile --windowed --icon=asl.ico CLEANER.py

Instalador via Inno Setup
O script .iss cria automaticamente a pasta C:\ASL\Image Cleaner, copia o executável, define o ícone personalizado e gera um atalho na área de trabalho, mantendo uma estrutura organizada e padronizada.

Módulo de Limpeza de Banco de Dados (SQL Server)

Além da limpeza de pastas, o Image Cleaner ASL conta com um módulo específico para manutenção de tabelas utilizadas no fluxo interno do PrintOnDemand. Esse módulo reduz drasticamente o acúmulo de registros antigos e melhora a performance do sistema.

O módulo oferece:

• Conexão por ODBC com SQL Server
O usuário configura servidor, banco, driver e credenciais diretamente pela interface. A conexão é validada antes de qualquer operação.

• Identificação Automática de Registros Obsoletos
Tabelas como JOBS, JOBS_DETAIL e JOB_HISTORICO são analisadas com validação de datas, integridade e dependências.

• Limpeza Segura com Transações SQL
Todas as exclusões ocorrem dentro de uma transação:
– Sucesso → commit imediato
– Qualquer erro → rollback automático
Garantindo preservação total da integridade do banco.

• Logs Detalhados das Operações
Cada ação no SQL Server gera registros específicos, permitindo acompanhamento técnico e auditoria.

• Persistência de Configurações
Dados de conexão são armazenados no SQLite local de forma segura, sem qualquer exposição de credenciais no código-fonte.

=======================================================================================
COMO USAR
=======================================================================================

Abra o Image Cleaner ASL e, na interface principal, defina ou confirme o caminho das pastas onde as imagens do PrintOnDemand estão armazenadas. Em seguida, utilize o botão Analisar para que o sistema realize a leitura completa das pastas, validando datas, tamanho total e integridade estrutural. Após revisar o resultado da análise, basta iniciar a limpeza selecionando Limpar, acompanhando em tempo real o progresso e consultando o log final ao término da operação.

O módulo de conexão com o SQL Server está integrado diretamente à interface da aplicação. A string de conexão é configurada pelo próprio usuário, garantindo flexibilidade e compatibilidade com diferentes ambientes. Após preencher os campos necessários, utilize o botão Testar Conexão para validar automaticamente a comunicação com o servidor e confirmar se o acesso ao banco está funcional antes de prosseguir com qualquer operação dependente de dados.

Segurança
O Image Cleaner ASL foi desenvolvido com foco absoluto em segurança operacional. Todos os diretórios são rigorosamente validados antes de qualquer exclusão, garantindo que nenhuma operação destrutiva seja executada por engano. Todos os procedimentos são registrados em logs detalhados para rastreamento completo, e o banco local permanece protegido e isolado. Qualquer ação que envolva exclusão é sempre explicitamente confirmada pelo usuário.

=======================================================================================
SOLUÇÃO DE PROBLEMAS
=======================================================================================
Este guia apresenta os problemas mais comuns encontrados no uso do Image Cleaner ASL e suas respectivas soluções de forma direta e objetiva.

---BANCO DE DADOS SQLITE---

Problema: O banco local .db3 não foi criado
Solução: Basta abrir o programa; o arquivo será gerado automaticamente na primeira execução.

Problema: Erro database is locked
Solução: Feche todas as instâncias do programa e confirme que o arquivo não está em uso por outro processo.

Problema: Falha no login mesmo com credenciais corretas
Solução: Execute o programa como administrador ou utilize python CLEANER.PY --reset-db para recriar o banco.

Problema: Perda das configurações salvas
Solução: Utilize o arquivo automático Cleaner.db3.backup, renomeando-o para Cleaner.db3.

---PASTAS E ARQUIVOS---

Problema: As pastas de destino não aparecem
Solução: Verifique se o usuário possui permissões adequadas de leitura no diretório configurado.

Problema: Erro “Pasta não encontrada”
Solução: Confirme o caminho em Configurações → Pasta de Imagens e verifique a existência do diretório.

Problema: Pastas não reconhecidas (formato inválido)
Solução: As pastas devem seguir exatamente o padrão AAAADDMM HHMM (exemplo: 20241225 1430).

Problema: Erro de permissão ao excluir pastas
Solução: Execute o programa como administrador ou ajuste as permissões da pasta.

Problema: “Acesso negado” durante a limpeza
Solução: Feche aplicativos que possam estar utilizando os arquivos, como visualizadores de imagem.

---CONEXÃO COM O SQL SERVER---

Problema: Falha ao conectar ao SQL Server
Solução: Confirme se o ODBC Driver 17 for SQL Server está instalado.

Problema: Timeout ao testar a conexão
Solução: Verifique firewall, permissões de rede e acessibilidade do servidor.

Problema: Erro de autenticação SQL
Solução: Confirme usuário e senha definidos na string de conexão e se a conta está ativa.

Problema: String de conexão inválida
Solução: Utilize o formato:
DRIVER={ODBC Driver 17 for SQL Server};SERVER=...;DATABASE=...;UID=...;PWD=...

---AUTENTICAÇÃO E ACESSO---

Problema: Login não funciona após a instalação
Solução: Use as credenciais padrão: usuário admin, senha 123.

Problema: Esqueci a senha de administrador
Solução: Execute python CLEANER.PY --reset-db para redefinir o banco (todos os usuários serão apagados).

Problema: Usuário bloqueado ou inativo
Solução: Um administrador deve reativar o usuário pelo painel do sistema.

Problema: Permissões insuficientes
Solução: Solicite elevação de acesso a um administrador.

---INTERFACE E EXECUÇÃO---

Problema: O programa não inicia (erro de importação)
Solução: Instale as dependências com pip install PySide6 pyodbc.

Problema: Interface congela durante análise
Solução: Aguarde; processos grandes podem levar tempo. A barra de progresso indica avanço.

Problema: Barra de progresso não se move
Solução: Pode ocorrer com milhares de pastas; o progresso é atualizado por lote.

Problema: “Application failed to start”
Solução: Instale o Visual C++ Redistributable mais recente.

Problema: Texto cortado ou layout distorcido
Solução: Ajuste a escala de exibição do Windows para 100%.

---ANÁLISE E LIMPEZA---
Problema: Nenhuma pasta encontrada
Solução: Verifique as datas selecionadas e o padrão do nome das pastas.

Problema: O banco mostra zero registros apesar de haver dados
Solução: Confirme que a conexão SQL está apontando para a instância e banco corretos.

Problema: A limpeza remove menos pastas do que o esperado
Solução: Algumas pastas podem estar em uso ou sem permissões; consulte os logs.

Problema: Erro durante transação do banco
Solução: O rollback é automático; verifique a conexão e tente novamente.

---LOGS E MONITORAMENTO---

Problema: Os logs não são gerados
Solução: Verifique permissões de escrita ou execute como administrador.

Problema: Arquivo de log muito grande
Solução: Limpe a pasta de logs ou compacte os arquivos periodicamente.

Problema: Não consigo visualizar logs antigos
Solução: O sistema utiliza rotação de logs; faça backup se for necessário histórico longo.

Problema: Mensagens de erro muito genéricas
Solução: Consulte o arquivo detalhado logs/log.txt.

---PERFORMANCE--- 

Problema: Análise muito lenta
Solução: Pastas com grande volume de arquivos podem exigir tempo; considere dividir por períodos.

Problema: Alto consumo de memória
Solução: Em processos com milhares de pastas, o uso temporário de RAM pode aumentar. Aguarde a conclusão.

Problema: O programa parece não responder
Solução: Operações de I/O intensas, especialmente via rede, podem causar lentidão temporária.


Para problemas de login:
Teste usuário admin e senha 123

Execute como administrador

Utilize --reset-db para recriar o banco

Verifique permissões na pasta do programa



📄 Licença
Ferramenta corporativa interna. É estritamente proibida qualquer forma de distribuição externa.

👤 Autor
Logan Barcelos
Analista de Suporte • Python Developer • Automação
Criador do Image Cleaner ASL.