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

# Create pi user with passwordless sudo
RUN useradd -m -s /bin/bash pi \
    && echo 'pi ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/pi \
    && chmod 440 /etc/sudoers.d/pi

# Install nixbash as pi
USER pi
RUN curl -sL https://raw.githubusercontent.com/nixfred/nixbash/main/install.sh | bash
USER root

# Copy tmux config for pi
COPY .tmux.conf /home/pi/.tmux.conf
RUN chown pi:pi /home/pi/.tmux.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
