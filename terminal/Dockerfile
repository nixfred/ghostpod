FROM tsl0922/ttyd:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    wget \
    git \
    vim \
    jq \
    tmux \
    sudo \
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
    ca-certificates \
    && ln -sf $(which fdfind) /usr/local/bin/fd \
    && rm -rf /var/lib/apt/lists/*

# Session user — non-root, with passwordless sudo for ergonomics
RUN useradd -m -s /bin/bash pi \
    && echo 'pi ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/pi \
    && chmod 440 /etc/sudoers.d/pi

# Bake in dotfiles. Sessions are ephemeral so no home volume.
COPY .bashrc /home/pi/.bashrc
COPY .tmux.conf /home/pi/.tmux.conf
RUN chown pi:pi /home/pi/.bashrc /home/pi/.tmux.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
