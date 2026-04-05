"""
Pydantic request / response models for the vault API.

All encrypted data is transferred as base64-encoded strings so that
binary blobs survive JSON serialisation.  The server NEVER receives
plaintext passwords — only opaque ciphertext blobs.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ── Vault key setup (wrapped DEK + Argon2id salt) ───────────────────────────


class VaultKeySetupRequest(BaseModel):
    """Client sends wrapped DEK + derivation salt on first vault creation."""
    wrapped_dek_b64: str = Field(
        ..., description="DEK encrypted with KEK, base64-encoded"
    )
    dek_nonce_b64: str = Field(
        ..., description="Nonce used for DEK wrapping, base64-encoded"
    )
    dek_tag_b64: str = Field(
        ..., description="Auth tag for DEK wrapping, base64-encoded"
    )
    kek_salt_b64: str = Field(
        ..., description="Salt used for Argon2id KEK derivation, base64-encoded"
    )


class VaultKeyResponse(BaseModel):
    """Server returns the stored wrapped DEK material."""
    exists: bool
    wrapped_dek_b64: Optional[str] = None
    dek_nonce_b64: Optional[str] = None
    dek_tag_b64: Optional[str] = None
    kek_salt_b64: Optional[str] = None


# ── Vault entries (encrypted blobs) ─────────────────────────────────────────


class VaultEntryCreateRequest(BaseModel):
    """Client sends a fully-encrypted entry blob."""
    encrypted_data_b64: str = Field(
        ..., description="AES-256-GCM ciphertext, base64-encoded"
    )
    nonce_b64: str = Field(
        ..., description="Nonce for this entry, base64-encoded"
    )
    tag_b64: str = Field(
        ..., description="Auth tag for this entry, base64-encoded"
    )


class VaultEntryUpdateRequest(BaseModel):
    encrypted_data_b64: str
    nonce_b64: str
    tag_b64: str


class VaultEntryItem(BaseModel):
    id: str
    encrypted_data_b64: str
    nonce_b64: str
    tag_b64: str
    created_at: int
    updated_at: int


class VaultEntryListResponse(BaseModel):
    ok: bool = True
    entries: list[VaultEntryItem]


class VaultEntryResponse(BaseModel):
    ok: bool = True
    entry: VaultEntryItem


class VaultMessageResponse(BaseModel):
    ok: bool = True
    message: str
