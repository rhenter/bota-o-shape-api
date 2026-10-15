# Bota o Shape API

Backend multi-tenant do **Bota o Shape!**, uma plataforma SaaS B2B para academias. A academia é a contratante; professores, nutricionistas e alunos usam o produto por vínculos e permissões do tenant. O aluno entra por convite e não possui checkout ou assinatura individual.

O projeto usa Django, Django REST Framework, PostgreSQL, JWT rotativo e OpenAPI. Cada recurso de negócio pertence a uma academia e toda API de domínio resolve o tenant ativo pelo vínculo autenticado e pelo cabeçalho `X-Tenant-ID`; um `tenant_id` arbitrário enviado no payload não concede acesso.

## Escopo implementado

- **Identidade e tenancy:** academias, unidades, usuário UUID, memberships multi-CNPJ, papéis acumuláveis, atribuições profissional/aluno, consentimentos, convite de uso único, recuperação de senha e auditoria.
- **Treinos:** equipamentos separados de exercícios, músculos, variações, mídia, modelos com dias/exercícios/séries, observação do professor por exercício, nota por série, publicação versionada, atribuição e execução idempotente.
- **Avaliações:** protocolos configuráveis, medidas brutas, sítio/lado/unidade/método, condições de coleta e relatórios que só comparam medições compatíveis.
- **Nutrição:** perfil e diário do aluno, hidratação, mensagens, plano qualitativo ou catalogado e versões imutáveis. Publicação exige papel de nutricionista, vínculo com o aluno, consentimento e CRN/UF verificado.
- **Composição alimentar:** fontes e lotes rastreáveis, alimentos e preparo, nutrientes por 100 g, medidas caseiras documentadas, receitas por rendimento e snapshots históricos. Valores ausentes continuam ausentes.
- **Cobrança B2B:** planos globais configuráveis, assinatura por academia, faturas, tentativas, eventos idempotentes e entitlements. A integração externa usa um adapter e permanece desabilitada até um provedor ser configurado.
- **Proteção:** soft delete de memberships, dados de saúde imutáveis após publicação/conclusão, rate limit, uploads limitados, headers de segurança, logs sem payloads sensíveis e pedidos auditáveis de exportação/exclusão.

O backend não gera treinos, dietas, metas, diagnósticos ou progressão por algoritmo. Dados de composição são estimativas descritivas; a prescrição e a interpretação continuam sob responsabilidade profissional.

## Requisitos e início rápido

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16+
- Redis 7+ apenas para cache/Celery quando habilitado

Suba os serviços locais, instale as dependências e prepare o banco:

```sh
cp local.env .env
docker compose up -d postgres redis
uv sync --extra postgres --group test
uv run python src/manage.py migrate
uv run python src/manage.py createsuperuser
uv run python src/manage.py runserver
```

A API inicia em `http://127.0.0.1:8000`. Os endpoints públicos principais são:

| Endpoint | Uso |
| --- | --- |
| `GET /api/core/health/` | Health check |
| `POST /api/tenancy/owner/register/` | Cria owner, tenant e piloto inicial sem preço fixo |
| `POST /api/user/auth/token/` | Login por e-mail/senha |
| `POST /api/user/auth/token/refresh/` | Rotaciona refresh token |
| `POST /api/user/auth/token/revoke/` | Revoga refresh token |
| `POST /api/tenancy/memberships/invite/` | Convida equipe ou aluno |
| `POST /api/tenancy/invitations/accept/` | Aceita convite de uso único |
| `GET /api/schema/` | OpenAPI JSON |
| `GET /api/docs/` | Swagger UI |

Exemplo de uma chamada autenticada em uma academia:

```sh
curl http://127.0.0.1:8000/api/workouts/assignments/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID"
```

Se a conta tiver apenas um membership ativo, o tenant pode ser inferido. Para contas com mais de uma academia, o cabeçalho é obrigatório. IDs de objetos de outro tenant retornam negação ou não são encontrados.

## Papéis e regras centrais

| Papel/escopo | Capacidades |
| --- | --- |
| `owner` / `admin` | Unidades, memberships e operações profissionais permitidas no tenant |
| `coach` | Catálogo, treino e avaliação de alunos atribuídos |
| `dietitian` | Nutrição de alunos atribuídos; publicar exige CRN/UF verificado |
| `student` | Somente os próprios treinos, avaliações liberadas, plano ativo e registros |
| `billing.manage` | Assinatura, portal e faturas da academia |

Uma pessoa pode acumular `coach` e `dietitian`. O papel administrativo não substitui habilitação clínica. Consentimento e atribuição ativa são checados em operações sensíveis.

## Desenvolvimento

```sh
make check       # checks do Django
make lint        # Ruff
make format      # formatação Ruff
make migrations  # confirma que não faltam migrations
make test        # pytest, cobertura e execução paralela
```

Para testar com SQLite isoladamente:

```sh
DATABASE_URL=sqlite:////tmp/botaoshape-test.sqlite3 uv run pytest -c src/pytest.ini src/tests -n 0
```

A suíte cobre isolamento de tenant, JWT/onboarding, convite sem cobrança de aluno, permissões, versões de treino e plano alimentar, observações por exercício/série, idempotência, comparação de medidas, snapshots alimentares e bloqueios de cobrança. A cobertura mínima configurada é 60%.

## Configuração

As variáveis do processo têm precedência sobre `.env`.

| Variável | Descrição |
| --- | --- |
| `SECRET_KEY`, `DEBUG`, `ENVIRONMENT` | Segurança e ambiente Django |
| `DATABASE_URL`, `DB_CONN_MAX_AGE` | PostgreSQL (SQLite é o fallback do código) |
| `CACHE_URL`, `CELERY_BROKER_URL` | Redis/cache e tarefas assíncronas |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` | Hosts e origens permitidas |
| `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS` | Validade de access/refresh; refresh é rotativo e revogável |
| `PASSWORD_RESET_TIMEOUT` | Expiração de redefinição de senha em segundos |
| `API_PAGE_SIZE`, `API_USER_RATE` | Paginação e rate limit por usuário |
| `MAX_UPLOAD_BYTES` | Limite global recebido pelo Django; mídia também valida extensão |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | Entrega de convite e redefinição |
| `USDA_API_KEY` | Chave server-side para a integração FoodData Central quando habilitada |
| `SECURE_*`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | HTTPS, cookies e HSTS |

Nunca coloque segredos no app Flutter, painel Next.js ou repositório. O adapter de cobrança padrão recusa checkout, portal e webhook; configure e teste um provedor hospedado antes de ativar self-service. Número completo de cartão e CVV não pertencem a este banco.

## Organização

```text
src/apps/
├── core/          # UUID/timestamps, auditoria e direitos do titular
├── user/          # usuário, JWT e recuperação de senha
├── tenancy/       # tenant, unidade, memberships, papéis, vínculos e consentimento
├── workouts/      # catálogo, prescrição, atribuição e execução
├── assessments/   # protocolos, medidas e relatórios compatíveis
├── food/          # fontes, alimentos, nutrientes, medidas e receitas
├── nutrition/     # planos versionados, diário, hidratação e mensagens
└── billing/       # planos, assinatura, faturas, eventos e entitlements
```

Mídia local fica em `src/frontend/media/` e não é versionada. Em produção, use storage privado/CDN com URLs assinadas e varredura de arquivos. Celery deve ser mantido apenas para tarefas assíncronas reais, como importações grandes ou notificações.

## Catálogo alimentar e licenças

TBCA é a fonte prioritária para itens brasileiros, mas este repositório não automatiza sua coleta nem redistribui dados. Formato, licença, atribuição e condições de uso ainda precisam de validação formal antes de importar um lote. USDA FoodData Central pode ser usado como complemento pela API oficial; a chave deve permanecer no backend, com cache, rate limit, rastreabilidade e tratamento de indisponibilidade.

Após obter um arquivo oficial e autorização compatível com o uso do produto, normalize-o como CSV UTF-8 com uma linha por alimento/nutriente. As colunas obrigatórias são `external_id`, `name`, `nutrient_code`, `nutrient_name`, `nutrient_unit` e `value_per_100g`; também são aceitas `preparation_state`, `edible_description`, `branded` e `data_type`. Valores ausentes podem ser representados por vazio, `-`, `NA`, `N/A`, `ND` ou `TR` e não são convertidos em zero.

```sh
uv run python src/manage.py import_food_table dados/tbca-7.3.csv \
  --source tbca \
  --source-version 7.3 \
  --attribution-url https://www.tbca.net.br/ \
  --license-status approved \
  --activate
```

Sem `--activate`, a fonte é importada desabilitada para permitir validação antes de aparecer no catálogo. O comando aceita CSV separado por vírgula ou ponto e vírgula, calcula o checksum do arquivo, registra `FoodImportBatch` e pode ser executado novamente sem duplicar alimentos ou nutrientes.

Alimento cru, cozido ou preparado é um registro distinto. Medida caseira só existe quando há conversão documentada para aquele item. O cálculo usa `valor_por_100g × gramas_comestíveis ÷ 100`; receitas somam ingredientes e dividem pelo rendimento final. Diário e plano guardam o snapshot, a fonte e a versão usados.

## Pendências antes de produção

Este código fornece controles técnicos, mas ainda requer trabalho operacional e jurídico:

- avaliação LGPD, bases legais, finalidades, retenção, anonimização e atendimento ao titular;
- política específica para menores; o MVP deve permanecer 18+ até essa governança existir;
- contratos com operadores, encarregado/canal, resposta a incidentes e backups restaurados em teste;
- revisão profissional de conteúdo de treino, protocolos e nutrição;
- validação das licenças TBCA/USDA e direitos de mídia;
- implementação do provedor de cobrança, verificação criptográfica real de webhook e conciliação;
- storage privado, antivírus, URLs assinadas, observabilidade sem dados de saúde e testes de carga;
- política contratual de carência, exportação, cancelamento e retenção por inadimplência.

Dados sensíveis não devem ser enviados a analytics ou LLMs. Eventos de auditoria registram ações e metadados mínimos, sem copiar medidas, refeições, fotos, tokens ou senhas.
