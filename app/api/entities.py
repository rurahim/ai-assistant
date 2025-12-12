"""
Entity API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Entity
from app.schemas.entity import (
    EntityResponse,
    EntityListResponse,
    EntityContextResponse,
    EntityCreateRequest,
    EntityUpdateRequest,
)
from app.services import EntityService

router = APIRouter(prefix="/entities")


async def get_user(db: AsyncSession, external_user_id: str) -> User:
    """Get user by external ID."""
    stmt = select(User).where(User.external_user_id == external_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/{user_id}", response_model=EntityListResponse)
async def list_entities(
    user_id: str,
    entity_type: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List entities for a user with optional type filter."""
    user = await get_user(db, user_id)

    entity_service = EntityService()
    entities, total = await entity_service.get_user_entities(
        db=db,
        user_id=user.id,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )

    return EntityListResponse(
        entities=[
            EntityResponse(
                id=str(e.id),
                name=e.name,
                type=e.entity_type,
                normalized_name=e.normalized_name,
                metadata=e.entity_metadata,
                mention_count=e.mention_count,
                last_seen_at=e.last_seen_at,
                created_at=e.created_at,
            )
            for e in entities
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}/{entity_id}", response_model=EntityResponse)
async def get_entity(
    user_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific entity."""
    user = await get_user(db, user_id)

    stmt = select(Entity).where(
        Entity.id == entity_id,
        Entity.user_id == user.id,
    )
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        type=entity.entity_type,
        normalized_name=entity.normalized_name,
        metadata=entity.entity_metadata,
        mention_count=entity.mention_count,
        last_seen_at=entity.last_seen_at,
        created_at=entity.created_at,
    )


@router.get("/{user_id}/{entity_id}/context")
async def get_entity_context(
    user_id: str,
    entity_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get all context related to an entity."""
    user = await get_user(db, user_id)

    entity_service = EntityService()
    context = await entity_service.get_entity_context(
        db=db,
        user_id=user.id,
        entity_id=entity_id,
        limit=limit,
    )

    if not context:
        raise HTTPException(status_code=404, detail="Entity not found")

    return context


@router.post("/{user_id}", response_model=EntityResponse)
async def create_entity(
    user_id: str,
    request: EntityCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually create an entity."""
    user = await get_user(db, user_id)

    # Check if entity already exists
    normalized = request.name.lower().strip()
    stmt = select(Entity).where(
        Entity.user_id == user.id,
        Entity.entity_type == request.type,
        Entity.normalized_name == normalized,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Entity '{request.name}' of type '{request.type}' already exists",
        )

    entity = Entity(
        user_id=user.id,
        entity_type=request.type,
        name=request.name,
        normalized_name=normalized,
        metadata=request.metadata,
        mention_count=0,
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)

    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        type=entity.entity_type,
        normalized_name=entity.normalized_name,
        metadata=entity.entity_metadata,
        mention_count=entity.mention_count,
        last_seen_at=entity.last_seen_at,
        created_at=entity.created_at,
    )


@router.patch("/{user_id}/{entity_id}", response_model=EntityResponse)
async def update_entity(
    user_id: str,
    entity_id: str,
    request: EntityUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update an entity."""
    user = await get_user(db, user_id)

    stmt = select(Entity).where(
        Entity.id == entity_id,
        Entity.user_id == user.id,
    )
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    if request.name:
        entity.name = request.name
        entity.normalized_name = request.name.lower().strip()

    if request.metadata:
        entity.entity_metadata = {**entity.entity_metadata, **request.metadata}

    await db.commit()
    await db.refresh(entity)

    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        type=entity.entity_type,
        normalized_name=entity.normalized_name,
        metadata=entity.entity_metadata,
        mention_count=entity.mention_count,
        last_seen_at=entity.last_seen_at,
        created_at=entity.created_at,
    )


@router.delete("/{user_id}/{entity_id}")
async def delete_entity(
    user_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete an entity."""
    user = await get_user(db, user_id)

    stmt = select(Entity).where(
        Entity.id == entity_id,
        Entity.user_id == user.id,
    )
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    await db.delete(entity)
    await db.commit()

    return {"deleted": True, "entity_id": entity_id}


@router.get("/{user_id}/search/{query}")
async def search_entities(
    user_id: str,
    query: str,
    entity_type: str = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Search entities by name."""
    user = await get_user(db, user_id)

    normalized = query.lower().strip()

    stmt = select(Entity).where(
        Entity.user_id == user.id,
        Entity.normalized_name.contains(normalized),
    )

    if entity_type:
        stmt = stmt.where(Entity.entity_type == entity_type)

    stmt = stmt.order_by(Entity.mention_count.desc()).limit(limit)

    result = await db.execute(stmt)
    entities = result.scalars().all()

    return {
        "query": query,
        "results": [
            {
                "id": str(e.id),
                "name": e.name,
                "type": e.entity_type,
                "metadata": e.entity_metadata,
                "mention_count": e.mention_count,
            }
            for e in entities
        ],
    }
