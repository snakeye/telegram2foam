CONTEXT_NAME ?= home-server
CONTEXT_HOST ?= ssh://snakeye@home-server
ENV_FILE ?= .env

COMPOSE = DOCKER_CONTEXT=$(CONTEXT_NAME) docker compose --env-file $(ENV_FILE)

.PHONY: context up down logs ps

context:
	@docker context inspect $(CONTEXT_NAME) >/dev/null 2>&1 || \
		docker context create $(CONTEXT_NAME) --docker "host=$(CONTEXT_HOST)"

up: context
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps
