FROM python:3.13-slim-bookworm AS base

ARG APP_HOME=/app

ARG BUILD_ENVIRONMENT="production"
ARG APP_VERSION="unknown"

WORKDIR $APP_HOME

ENV BUILD_ENVIRONMENT=$BUILD_ENVIRONMENT
ENV APP_VERSION=$APP_VERSION
ENV PYTHONUNBUFFERED=1s
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIPENV_VENV_IN_PROJECT=1
ENV PIPENV_CACHE_DIR=/root/.cache/pip
ENV PATH=$APP_HOME/.venv/bin:$PATH


FROM base AS builder

RUN python -m venv $APP_HOME/.venv
COPY Pipfile Pipfile.lock $APP_HOME/
RUN --mount=type=cache,target=/root/.cache/pip pip install pipenv==2024.4.0
RUN --mount=type=cache,target=/root/.cache/pip pipenv install --deploy --categories "packages"


FROM base AS runtime

RUN addgroup --system django \
  && adduser --system --ingroup django django

RUN chown django:django $APP_HOME

COPY --from=builder --chown=django:django $APP_HOME/.venv $APP_HOME/.venv

COPY --chmod=0755 --chown=django:django ./scripts/*.sh $APP_HOME

COPY --chown=django:django . $APP_HOME

USER django

EXPOSE 8090
