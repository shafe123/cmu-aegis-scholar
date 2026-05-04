"""Configuration settings for the Identity API service."""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DOCKER_SECRETS_PATH = "/run/secrets"
SECRETS_DIR = DOCKER_SECRETS_PATH if os.path.exists(DOCKER_SECRETS_PATH) else None


class Settings(BaseSettings):
    """Configuration settings for the Identity API."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", secrets_dir=SECRETS_DIR, extra="ignore"
    )

    # API Configuration
    api_title: str = "Aegis Scholar Identity API"
    api_version: str = "1.0.0"
    api_description: str = (
        "LDAP-based identity and authentication service for managing research authors and organizations"
    )
    api_port: int = 8005

    # LDAP Configuration
    ldap_server: str = Field(default="ldap://ldap-server:389", validation_alias="LDAP_SERVER")
    ldap_admin_dn: str = Field(default="cn=admin,dc=example,dc=org", validation_alias="LDAP_ADMIN_DN")
    ldap_admin_password: str = Field(default="admin", validation_alias="LDAP_ADMIN_PASSWORD")
    ldap_base_dn: str = Field(default="dc=example,dc=org", validation_alias="LDAP_BASE_DN")

    # Data File Configuration
    auth_jsonl_file_path: str = Field(
        default="/data/dtic_compressed/dtic_authors_001.jsonl.gz", validation_alias="AUTH_JSONL_FILE_PATH"
    )
    org_jsonl_file_path: str = Field(
        default="/data/dtic_compressed/dtic_orgs_001.jsonl.gz", validation_alias="ORG_JSONL_FILE_PATH"
    )

    # Email Domain Configuration
    email_domains: list[str] = [
        "dtic.mil",
        "navy.mil",
        "army.mil",
        "af.mil",
        "usmc.mil",
        "university.edu",
        "us.gov",
    ]


settings = Settings()
