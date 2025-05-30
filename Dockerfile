# Dockerfile for Debian Bookworm with XFCE and TigerVNC

FROM debian:bookworm-slim

# Prevent debconf from asking questions during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Default VNC password and user settings
# IMPORTANT: Override VNC_PASSWORD at runtime for security, e.g., -e VNC_PASSWORD=yoursecurepassword
ENV VNC_PASSWORD=123456
ENV USER_NAME=debian
ENV HOME_DIR=/home/debian

# Install dependencies: XFCE, TigerVNC, sudo, and other utilities
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tigervnc-standalone-server \
    tigervnc-common \
    tigervnc-tools \
    firefox-esr \
    xfce4 \
    xfce4-goodies \
    dbus-x11 \
    sudo \
    iproute2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user and set its password (using VNC_PASSWORD)
# Grant sudo privileges to the user (useful for debugging within the container)
RUN useradd -m -s /bin/bash ${USER_NAME} && \
    echo "${USER_NAME}:${VNC_PASSWORD}" | chpasswd && \
    echo "${USER_NAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -pv /etc/tigervnc && \
    echo ":1=debian" > /etc/tigervnc/vncserver.users && \
    echo '1;' > /etc/tigervnc/vncserver-config-defaults && \
    echo '$localhost="no";' >> /etc/tigervnc/vncserver-config-defaults && \
    echo '$SecurityTypes="VncAuth,Plain";' >> /etc/tigervnc/vncserver-config-defaults && \
    echo '$geometry="800x600";' >> /etc/tigervnc/vncserver-config-defaults && \
    echo 'alwaysshared;' >> /etc/tigervnc/vncserver-config-defaults # Allow multiple viewers to connect

# Switch to the non-root user
USER ${USER_NAME}
WORKDIR ${HOME_DIR}

# Configure VNC server for the user
RUN mkdir -p ${HOME_DIR}/.vnc && \
    # Set VNC password
    echo "${VNC_PASSWORD}\n\n" | vncpasswd -f > ${HOME_DIR}/.vnc/passwd && \
    chmod 600 ${HOME_DIR}/.vnc/passwd

# Create VNC xstartup script to launch XFCE desktop environment
RUN echo '#!/bin/sh' > ${HOME_DIR}/.vnc/xstartup && \
    echo '# Ensure Xresources are loaded if they exist' >> ${HOME_DIR}/.vnc/xstartup && \
    echo '[ -r $HOME/.Xresources ] && xrdb $HOME/.Xresources' >> ${HOME_DIR}/.vnc/xstartup && \
    echo '# Start vncconfig for clipboard integration etc.' >> ${HOME_DIR}/.vnc/xstartup && \
    echo 'vncconfig -iconic &' >> ${HOME_DIR}/.vnc/xstartup && \
    echo '# Launch XFCE session with D-Bus' >> ${HOME_DIR}/.vnc/xstartup && \
    echo 'dbus-launch --exit-with-session startxfce4' >> ${HOME_DIR}/.vnc/xstartup && \
    chmod +x ${HOME_DIR}/.vnc/xstartup

# Expose VNC port (default for display :1 is 5901)
EXPOSE 5901

# Default command to run VNC server on display :1 in the foreground
# This will use settings from ${HOME_DIR}/.vnc/config
CMD ["/usr/bin/vncserver", ":1", "-fg"]
