FROM tsl0922/ttyd:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    wget \
    git \
    vim \
    jq \
    tmux \
    # networking
    openssh-client \
    iproute2 \
    iputils-ping \
    dnsutils \
    netcat-openbsd \
    net-tools \
    mtr-tiny \
    # process / system
    htop \
    procps \
    less \
    unzip \
    ripgrep \
    fd-find \
    # shell
    zsh \
    zsh-autosuggestions \
    zsh-syntax-highlighting \
    ca-certificates \
    && ln -sf $(which fdfind) /usr/local/bin/fd \
    && rm -rf /var/lib/apt/lists/*

# Install Starship
RUN curl -sS https://starship.rs/install.sh | sh -s -- --yes

# Dotfiles are baked in — sessions are ephemeral, no home volume
RUN mkdir -p /root/.config
COPY .zshrc /root/.zshrc
COPY starship.toml /root/.config/starship.toml
COPY .tmux.conf /root/.tmux.conf

RUN chsh -s $(which zsh)

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
