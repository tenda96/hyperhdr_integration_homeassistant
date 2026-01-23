"""Costanti per l'integrazione HyperHDR Simple."""

DOMAIN = "hyperhdr_integration"
DEFAULT_PORT = 12000
DEFAULT_NAME = "HyperHDR"

# Chiavi di configurazione
CONF_HOST = "host"
CONF_PORT = "port"
CONF_TOKEN = "token"
CONF_NAME = "name"  # <--- QUESTA MANCAVA E CAUSAVA IL CRASH