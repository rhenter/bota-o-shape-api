# Bota o Shape API

API do Bota o Shape, construída com Django e Django REST Framework. O código da aplicação fica em `src/`.

## Requisitos

- Python 3.14 ou superior;
- [uv](https://docs.astral.sh/uv/) para instalar as dependências e executar os comandos;
- PostgreSQL e Redis somente se você optar pelas integrações correspondentes.

## Início rápido

Em um repositório novo, copie os arquivos desta base. Ajuste o nome do projeto em `pyproject.toml`, `APP_NAME` em `local.env` e a descrição deste README. Então, na raiz do projeto:

```sh
cp local.env .env
uv sync --group test
uv run python src/manage.py check
uv run python src/manage.py makemigrations user
uv run python src/manage.py migrate
uv run pytest -c src/pytest.ini src/tests
uv run python src/manage.py runserver
```

O servidor de desenvolvimento usa `http://127.0.0.1:8000/`. Acesse `/api/core/health/` para verificar se a aplicação responde. Para usar o admin em `/admin/`, crie um superusuário com `uv run python src/manage.py createsuperuser` após aplicar as migrações.

**Gere e versione `src/apps/user/migrations/0001_initial.py` antes da primeira migração do banco.** O boilerplate define `AUTH_USER_MODEL = "user.User"` e não inclui migrações. Mudar o modelo de usuário depois de criar as tabelas exige uma migração mais complexa. Execute `makemigrations user` antes de `migrate` e dos testes que acessam o banco.

## Estrutura

```text
botaoshape-api/
├── .gitignore
├── Makefile
├── README.md
├── local.env
├── pyproject.toml
├── uv.lock
└── src/
    ├── apps/
    │   ├── core/             # Modelo abstrato com timestamps e health check
    │   └── user/             # Modelo de usuário, admin e API
    ├── django_settings/      # Configuração, URLs, ASGI, WSGI e Celery
    ├── frontend/
    │   ├── static/           # Arquivos CSS, JS e imagens de origem
    │   └── templates/        # Templates HTML
    ├── locale/               # Traduções
    ├── tests/test_smoke.py
    ├── .coveragerc
    ├── manage.py
    └── pytest.ini
```

`src/frontend/media/` guarda uploads em execução; `src/staticfiles/` recebe a saída de `collectstatic`. Ambas são ignoradas no Git. O pacote de configuração chama-se `django_settings`. Se você o renomear, atualize as referências em `manage.py`, `asgi.py`, `wsgi.py`, `celery.py`, `pytest.ini` e `settings.py`.

## Recursos disponíveis

| Recurso | Comportamento |
| --- | --- |
| `GET /api/core/health/` | Retorna `{"status": "ok"}` sem autenticação. |
| `/api/user/users/` | Lista, consulta, cria e atualiza usuários. Todas as ações exigem `is_staff`; não há cadastro público nem exclusão pela API. |
| `User(AbstractUser)` | Modelo customizado registrado no admin. A criação e a atualização pela API validam a senha e a armazenam por hash. |
| Django REST Framework | Autenticação por sessão e permissão de usuário autenticado por padrão; paginação, busca, ordenação e filtros configurados. |
| Banco, cache e arquivos | SQLite, cache em memória e arquivos locais por padrão; PostgreSQL e Redis podem ser configurados por ambiente. |
| Celery | Aplicação configurada e autodiscovery de tarefas; requer um broker em execução para processá-las. |
| Django Celery Logs | Registra execuções e falhas das tarefas no banco e permite consultá-las no admin. |

O `core` também fornece `TimestampedModel`, uma classe abstrata opcional com `created_at` e `updated_at`. As URLs registram apenas o admin padrão e as duas apps iniciais. A base não traz `admin_custom.py`, tarefas de domínio ou integrações privadas do Hydrostats.

## Configuração

`local.env` é um exemplo: copie-o para `.env` e ajuste os valores. O arquivo `.env` não deve ser versionado. As variáveis já definidas no processo têm precedência sobre o arquivo.

| Variável | Uso |
| --- | --- |
| `SECRET_KEY` | Obrigatória. Substitua a chave de desenvolvimento antes de publicar; a aplicação recusa chaves iniciadas por `django-insecure-` com `DEBUG=False`. |
| `DEBUG`, `ENVIRONMENT`, `APP_NAME`, `APP_VERSION` | Modo de desenvolvimento e identificação da aplicação. `DEBUG` é falso por padrão. |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_CREDENTIALS` | Hosts e origens permitidos. Listas usam valores separados por vírgula. |
| `DATABASE_URL`, `DB_CONN_MAX_AGE` | Banco de dados e persistência de conexões. Sem URL, usa SQLite na raiz. |
| `CACHE_URL` | Habilita cache Redis; sem URL, usa cache em memória. |
| `CELERY_BROKER_URL` | Broker das tarefas. O padrão é `redis://localhost:6379/0`. Os resultados do Celery são ignorados; o histórico fica no Django Celery Logs. |
| `LANGUAGE_CODE`, `TIME_ZONE`, `API_PAGE_SIZE` | Idioma, fuso horário e tamanho da página da API. |
| `STATIC_URL`, `MEDIA_URL` | URLs de arquivos estáticos e uploads. |
| `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | Opções de HTTPS e cookies para o ambiente de implantação. |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `LOG_LEVEL` | E-mail e nível dos logs. |

Para PostgreSQL, instale o extra e defina `DATABASE_URL` antes de executar as migrações:

```sh
uv sync --extra postgres --group test
```

Redis só é necessário quando `CACHE_URL` aponta para ele ou quando tarefas Celery usam um broker Redis. Antes de publicar, configure a chave secreta, hosts, origens e opções de HTTPS para o ambiente; execute `uv run python src/manage.py check --deploy` e `uv run python src/manage.py collectstatic`. A publicação dos arquivos estáticos e de mídia depende da infraestrutura escolhida.

Para registrar tarefas com o [Django Celery Logs](https://github.com/rhenter/django-celery-logs), aplique as migrações e inicie um worker com o broker em execução:

```sh
uv run python src/manage.py migrate
uv run celery --workdir src -A django_settings worker --loglevel=info
```

As execuções aparecem no admin em `/admin/`. A biblioteca fornece `clear_celery_task_logs` para limpar registros antigos; agende essa tarefa se precisar de retenção automática e configure `CELERY_TASK_LOGS_EXPIRES` com o número de dias desejado. O boilerplate usa `CELERY_TASK_IGNORE_RESULT = True`, portanto código que consulte `AsyncResult` precisará de um backend de resultados próprio.

## Comandos de desenvolvimento

O `Makefile` oferece os mesmos comandos do início rápido:

| Alvo | Ação |
| --- | --- |
| `make deps` | Instala as dependências com o grupo de testes. |
| `make check` | Executa as verificações do Django. |
| `make migrations` | Gera migrações da app `user`. |
| `make migrate` | Aplica as migrações. |
| `make test` | Executa `pytest -c src/pytest.ini src/tests`. |
| `make run` | Inicia o servidor de desenvolvimento. |

Os testes usam execução paralela, reutilização do banco e cobertura mínima de 60% sobre `apps`, conforme `src/pytest.ini` e `src/.coveragerc`.

## Adaptação da base

Adicione apps, dependências e serviços de domínio conforme as necessidades do novo projeto. Se não usar Celery, remova `src/django_settings/celery.py`, sua importação em `src/django_settings/__init__.py`, as opções `CELERY_*` em `settings.py`, a app `django_celery_logs` de `INSTALLED_APPS` e as dependências de Celery e Django Celery Logs do `pyproject.toml`.

Quando validada em um projeto novo, esta base pode ser guardada em um [repositório template do GitHub](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository). Uma skill pode orientar a criação do repositório, a troca de identificadores, a seleção de integrações e as verificações, apontando para o template como fonte única do código inicial.

Referências: [modelo de usuário customizado no Django](https://docs.djangoproject.com/en/6.1/topics/auth/customizing/) e [skills na documentação da OpenAI](https://developers.openai.com/plugins/build/skills).
