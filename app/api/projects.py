"""
Projects API — CRUD for Cipher's project filing system.
Syncs with iOS ProjectStore.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ProjectRecord, ProjectServiceRecord, ServiceCredentialRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ServiceConfig(BaseModel):
    id: Optional[str] = None
    service_type: str
    credential_id: Optional[str] = None
    config: Optional[dict] = None


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: str = "folder.fill"
    color: str = "blue"
    platform: str = "other"
    repo_url: Optional[str] = None
    deploy_url: Optional[str] = None
    railway_project_id: Optional[str] = None
    services: List[ServiceConfig] = []


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    platform: Optional[str] = None
    repo_url: Optional[str] = None
    deploy_url: Optional[str] = None
    railway_project_id: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    icon: str
    color: str
    platform: str
    repo_url: Optional[str]
    deploy_url: Optional[str]
    railway_project_id: Optional[str]
    services: List[ServiceConfig]
    created_at: str
    updated_at: str


class CredentialCreate(BaseModel):
    name: str
    service_type: str
    token_value: str
    project_id: Optional[str] = None
    additional_fields: Optional[dict] = None


class CredentialResponse(BaseModel):
    id: str
    name: str
    service_type: str
    project_id: Optional[str]
    additional_fields: Optional[dict]
    created_at: str
    last_used_at: Optional[str]
    # token_value intentionally excluded from response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _project_to_response(p: ProjectRecord) -> ProjectResponse:
    services = []
    for s in p.services:
        services.append(ServiceConfig(
            id=s.id,
            service_type=s.service_type,
            credential_id=s.credential_id,
            config=json.loads(s.config) if s.config else None,
        ))
    return ProjectResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        icon=p.icon,
        color=p.color,
        platform=p.platform,
        repo_url=p.repo_url,
        deploy_url=p.deploy_url,
        railway_project_id=p.railway_project_id,
        services=services,
        created_at=p.created_at.isoformat() if p.created_at else "",
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(db: Session = Depends(get_db)):
    """List all projects."""
    projects = db.query(ProjectRecord).order_by(ProjectRecord.updated_at.desc()).all()
    return [_project_to_response(p) for p in projects]


@router.post("/", response_model=ProjectResponse)
async def create_project(req: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project."""
    project = ProjectRecord(
        name=req.name,
        description=req.description,
        icon=req.icon,
        color=req.color,
        platform=req.platform,
        repo_url=req.repo_url,
        deploy_url=req.deploy_url,
        railway_project_id=req.railway_project_id,
    )
    db.add(project)
    db.flush()  # Get the ID

    # Add services
    for svc in req.services:
        db.add(ProjectServiceRecord(
            project_id=project.id,
            service_type=svc.service_type,
            credential_id=svc.credential_id,
            config=json.dumps(svc.config) if svc.config else None,
        ))

    db.commit()
    db.refresh(project)
    logger.info(f"Created project: {project.name} ({project.id})")
    return _project_to_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get a single project by ID."""
    project = db.query(ProjectRecord).filter(ProjectRecord.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, req: ProjectUpdate, db: Session = Depends(get_db)):
    """Update a project's metadata."""
    project = db.query(ProjectRecord).filter(ProjectRecord.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    logger.info(f"Updated project: {project.name}")
    return _project_to_response(project)


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project and its services."""
    project = db.query(ProjectRecord).filter(ProjectRecord.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    logger.info(f"Deleted project: {project.name}")
    return {"status": "deleted", "id": project_id}


# ---------------------------------------------------------------------------
# Credential endpoints
# ---------------------------------------------------------------------------

@router.get("/credentials/all", response_model=List[CredentialResponse])
async def list_credentials(db: Session = Depends(get_db)):
    """List all stored credentials (tokens redacted)."""
    creds = db.query(ServiceCredentialRecord).order_by(ServiceCredentialRecord.created_at.desc()).all()
    return [CredentialResponse(
        id=c.id,
        name=c.name,
        service_type=c.service_type,
        project_id=c.project_id,
        additional_fields=json.loads(c.additional_fields) if c.additional_fields else None,
        created_at=c.created_at.isoformat() if c.created_at else "",
        last_used_at=c.last_used_at.isoformat() if c.last_used_at else None,
    ) for c in creds]


@router.post("/credentials", response_model=CredentialResponse)
async def create_credential(req: CredentialCreate, db: Session = Depends(get_db)):
    """Store a new service credential."""
    cred = ServiceCredentialRecord(
        name=req.name,
        service_type=req.service_type,
        token_value=req.token_value,
        project_id=req.project_id,
        additional_fields=json.dumps(req.additional_fields) if req.additional_fields else None,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    logger.info(f"Stored credential: {cred.name} ({cred.service_type})")
    return CredentialResponse(
        id=cred.id,
        name=cred.name,
        service_type=cred.service_type,
        project_id=cred.project_id,
        additional_fields=req.additional_fields,
        created_at=cred.created_at.isoformat() if cred.created_at else "",
        last_used_at=None,
    )


@router.delete("/credentials/{credential_id}")
async def delete_credential(credential_id: str, db: Session = Depends(get_db)):
    """Delete a stored credential."""
    cred = db.query(ServiceCredentialRecord).filter(ServiceCredentialRecord.id == credential_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    db.delete(cred)
    db.commit()
    logger.info(f"Deleted credential: {cred.name}")
    return {"status": "deleted", "id": credential_id}
