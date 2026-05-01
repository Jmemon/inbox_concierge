"""Bucket HTTP API. Four routes: GET / POST / PATCH / DELETE."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.models import User, Bucket
from app.db.session import get_db
from app.deps import get_current_user
from app.inbox import bucket_repo


router = APIRouter(prefix="/api", tags=["buckets"])
log = logging.getLogger(__name__)


def _serialize(b: Bucket) -> dict:
    return {"id": b.id, "name": b.name, "criteria": b.criteria, "is_default": b.user_id is None}


class _ExampleIn(BaseModel):
    sender: str = ""
    subject: str = ""
    snippet: str = ""
    rationale: str = ""


class _CreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    confirmed_positives: list[_ExampleIn] = Field(default_factory=list)
    confirmed_negatives: list[_ExampleIn] = Field(default_factory=list)


class _PatchBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)


def _load_owned_or_403(db: Session, user_id: str, bucket_id: str) -> Bucket:
    """Load a bucket the user can mutate (PATCH/DELETE). Default → 403,
    other-user → 403, missing/soft-deleted → 404."""
    b = bucket_repo.get_by_id(db, bucket_id)
    if b is None:
        raise HTTPException(404, "not found")
    if b.user_id is None:
        raise HTTPException(403, "cannot modify default bucket")
    if b.user_id != user_id:
        raise HTTPException(403, "not your bucket")
    if b.is_deleted:
        raise HTTPException(404, "not found")
    return b


@router.get("/buckets")
def list_buckets(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = bucket_repo.list_active(db, user_id=user.id)
    return {"buckets": [_serialize(b) for b in rows]}


@router.post("/buckets", status_code=201)
def create_bucket(body: _CreateBody, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> dict:
    criteria = bucket_repo.formulate_criteria(
        description=body.description,
        confirmed_positives=[e.model_dump() for e in body.confirmed_positives],
        confirmed_negatives=[e.model_dump() for e in body.confirmed_negatives],
    )
    row = bucket_repo.create_custom(db, user_id=user.id, name=body.name, criteria=criteria)
    db.commit()
    return _serialize(row)


@router.patch("/buckets/{bucket_id}")
def patch_bucket(bucket_id: str, body: _PatchBody,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    b = _load_owned_or_403(db, user.id, bucket_id)
    bucket_repo.rename(db, b, body.name); db.commit()
    return _serialize(b)


@router.delete("/buckets/{bucket_id}", status_code=204)
def delete_bucket(bucket_id: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> None:
    # Don't 404 on already-deleted — DELETE is idempotent.
    b = bucket_repo.get_by_id(db, bucket_id)
    if b is None: raise HTTPException(404, "not found")
    if b.user_id is None: raise HTTPException(403, "cannot delete default bucket")
    if b.user_id != user.id: raise HTTPException(403, "not your bucket")
    if b.is_deleted: return
    bucket_repo.soft_delete(db, b); db.commit()
