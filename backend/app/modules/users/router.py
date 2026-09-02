from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.deps import get_db, get_current_user, RoleChecker
from app.modules.users.models import User
from app.modules.users.schemas import UserResponse, UserUpdate, UserRoleUpdate

router = APIRouter(prefix="/users", tags=["users"])

admin_only = RoleChecker(['Administrator'])

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
def update_users_me(user_update: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user_update.name is not None:
        current_user.name = user_update.name
    if user_update.organization is not None:
        current_user.organization = user_update.organization

    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("", response_model=List[UserResponse])
def list_users(
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    """Lists users, newest first. `limit`/`offset` are optional -- omitted
    returns every user, unchanged from before pagination was added."""
    query = db.query(User).order_by(User.created_at.desc()).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return query.all()

@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(user_id: int, role_update: UserRoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(admin_only)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role_update.role
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_only)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
