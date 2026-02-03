FROM mcr.microsoft.com/devcontainers/python:3.12

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
    gnupg \
    lsb-release \
    apt-transport-https \
  && rm -rf /var/lib/apt/lists/*

# Install Azure CLI
RUN python -m pip install azure-cli

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
  && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
  && rm kubectl

# Install Terraform
ARG TERRAFORM_VERSION=1.14.4
RUN curl -fsSL -o /tmp/terraform.zip https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip \
  && unzip /tmp/terraform.zip -d /usr/local/bin \
  && rm /tmp/terraform.zip

# Ensure pip tooling is up-to-date
RUN python -m pip install --upgrade pip setuptools wheel

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/*

# Install Poetry
ARG POETRY_VERSION=1.8.3
ENV POETRY_HOME="/etc/poetry"
ENV PATH="$POETRY_HOME/bin:/usr/local/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION} \
  && ln -sf $POETRY_HOME/bin/poetry /usr/local/bin/poetry \
  && poetry --version

# Configure Poetry to install into system environment in container builds
RUN poetry config virtualenvs.create false --local || true

USER vscode
