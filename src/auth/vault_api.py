"""
REST endpoints for the encrypted vault.

Zero-knowledge architecture: the server stores and returns opaque
ciphertext blobs.  It NEVER has access to the DEK or plaintext
passwords.  All encryption / decryption happens client-side.

Routes
------
POST   /vault/key              — store wrapped DEK + salt (first-time setup)
GET    /vault/key              — retrieve wrapped DEK + salt
PUT    /vault/key              — re-wrap DEK (master password change)
GET    /vault/entries          — list all user's encrypted entries
POST   /vault/entries          — create a new encrypted entry
PUT    /vault/entries/{id}     — update an encrypted entry
DELETE /vault/entries/{id}     — delete an entry
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.dependencies import get_auth_service, get_current_user
from src.auth.schemas import UserResponse
from src.auth.vault_schemas import (
    VaultEntryCreateRequest,
    VaultEntryItem,
    VaultEntryListResponse,
    VaultEntryResponse,
    VaultEntryUpdateRequest,
    VaultKeyResponse,
    VaultKeySetupRequest,
    VaultMessageResponse,
)

router = APIRouter(prefix="/vault", tags=["vault"])


def _get_db():
    """Access the shared AuthDatabase singleton (has vault tables)."""
    from src.auth.dependencies import database
    return database


# ═════════════════════════════════════════════════════════════════════════════
# VAULT KEY MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/key", response_model=VaultMessageResponse, status_code=status.HTTP_201_CREATED)
def vault_setup_key(
    payload: VaultKeySetupRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Store the wrapped DEK + KEK salt for first-time vault setup."""
    db = _get_db()
    with db.connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM vault_keys WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vault key already exists. Use PUT to re-wrap.",
            )
        now = int(time.time())
        conn.execute(
            """INSERT INTO vault_keys
               (user_id, wrapped_dek, dek_nonce, dek_tag, kek_salt, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                current_user.id,
                payload.wrapped_dek_b64,
                payload.dek_nonce_b64,
                payload.dek_tag_b64,
                payload.kek_salt_b64,
                now,
                now,
            ),
        )
    return VaultMessageResponse(message="Vault key stored successfully.")


@router.get("/key", response_model=VaultKeyResponse)
def vault_get_key(
    current_user: UserResponse = Depends(get_current_user),
):
    """Retrieve the wrapped DEK material for the authenticated user."""
    db = _get_db()
    with db.connection() as conn:
        row = conn.execute(
            "SELECT wrapped_dek, dek_nonce, dek_tag, kek_salt FROM vault_keys WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()
    if not row:
        return VaultKeyResponse(exists=False)
    return VaultKeyResponse(
        exists=True,
        wrapped_dek_b64=row["wrapped_dek"],
        dek_nonce_b64=row["dek_nonce"],
        dek_tag_b64=row["dek_tag"],
        kek_salt_b64=row["kek_salt"],
    )


@router.put("/key", response_model=VaultMessageResponse)
def vault_rewrap_key(
    payload: VaultKeySetupRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Re-wrap the DEK (e.g. after master password change)."""
    db = _get_db()
    with db.connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM vault_keys WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No vault key found. Use POST to create one first.",
            )
        conn.execute(
            """UPDATE vault_keys
               SET wrapped_dek = ?, dek_nonce = ?, dek_tag = ?,
                   kek_salt = ?, updated_at = ?
               WHERE user_id = ?""",
            (
                payload.wrapped_dek_b64,
                payload.dek_nonce_b64,
                payload.dek_tag_b64,
                payload.kek_salt_b64,
                int(time.time()),
                current_user.id,
            ),
        )
    return VaultMessageResponse(message="Vault key re-wrapped successfully.")


# ═════════════════════════════════════════════════════════════════════════════
# VAULT ENTRIES CRUD
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/entries", response_model=VaultEntryListResponse)
def vault_list_entries(
    current_user: UserResponse = Depends(get_current_user),
):
    """List ALL encrypted vault entries for the authenticated user."""
    db = _get_db()
    with db.connection() as conn:
        rows = conn.execute(
            """SELECT id, encrypted_data, nonce, tag, created_at, updated_at
               FROM vault_entries
               WHERE user_id = ?
               ORDER BY created_at DESC""",
            (current_user.id,),
        ).fetchall()
    entries = [
        VaultEntryItem(
            id=row["id"],
            encrypted_data_b64=row["encrypted_data"],
            nonce_b64=row["nonce"],
            tag_b64=row["tag"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
    return VaultEntryListResponse(entries=entries)


@router.post("/entries", response_model=VaultEntryResponse, status_code=status.HTTP_201_CREATED)
def vault_create_entry(
    payload: VaultEntryCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Store a new encrypted vault entry."""
    entry_id = str(uuid.uuid4())
    now = int(time.time())
    db = _get_db()
    with db.connection() as conn:
        conn.execute(
            """INSERT INTO vault_entries
               (id, user_id, encrypted_data, nonce, tag, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                entry_id,
                current_user.id,
                payload.encrypted_data_b64,
                payload.nonce_b64,
                payload.tag_b64,
                now,
                now,
            ),
        )
    return VaultEntryResponse(
        entry=VaultEntryItem(
            id=entry_id,
            encrypted_data_b64=payload.encrypted_data_b64,
            nonce_b64=payload.nonce_b64,
            tag_b64=payload.tag_b64,
            created_at=now,
            updated_at=now,
        ),
    )


@router.put("/entries/{entry_id}", response_model=VaultEntryResponse)
def vault_update_entry(
    entry_id: str,
    payload: VaultEntryUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Update an encrypted vault entry (only if owned by the user)."""
    db = _get_db()
    now = int(time.time())
    with db.connection() as conn:
        existing = conn.execute(
            "SELECT user_id, created_at FROM vault_entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found.")
        if existing["user_id"] != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        conn.execute(
            """UPDATE vault_entries
               SET encrypted_data = ?, nonce = ?, tag = ?, updated_at = ?
               WHERE id = ?""",
            (
                payload.encrypted_data_b64,
                payload.nonce_b64,
                payload.tag_b64,
                now,
                entry_id,
            ),
        )
        created_at = existing["created_at"]
    return VaultEntryResponse(
        entry=VaultEntryItem(
            id=entry_id,
            encrypted_data_b64=payload.encrypted_data_b64,
            nonce_b64=payload.nonce_b64,
            tag_b64=payload.tag_b64,
            created_at=created_at,
            updated_at=now,
        ),
    )


@router.delete("/entries/{entry_id}", response_model=VaultMessageResponse)
def vault_delete_entry(
    entry_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a vault entry (only if owned by the user)."""
    db = _get_db()
    with db.connection() as conn:
        existing = conn.execute(
            "SELECT user_id FROM vault_entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found.")
        if existing["user_id"] != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        conn.execute("DELETE FROM vault_entries WHERE id = ?", (entry_id,))
    return VaultMessageResponse(message="Entry deleted successfully.")
