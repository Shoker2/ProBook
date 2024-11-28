from fastapi import Depends, HTTPException, status, Request
import re

from ..schemas import UserToken
from ..auth import get_current_user

def get_current_user_with_perms(
        needble_permissions: list[str],
        user: UserToken = Depends(get_current_user),
    ) -> UserToken:

    if user.is_superuser:
        return user
    
    elif user.group is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN
        )

    for perm in needble_permissions:
        if not checking_for_permission(perm, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN
            )
    
    return user

def checking_for_permission(perm: str, user: UserToken) -> bool:
    if user.is_superuser:
        return True
    elif user.group is None:
        return False
    
    perms = user.group.permissions
    result = False
    
    for p in perms:
        is_negative = p.startswith('!')
        p_clean = p.lstrip('!')
        
        pattern = '^' + re.escape(p_clean).replace(r'\*', '.*') + '$'
        
        if re.match(pattern, perm) or perm.startswith(p_clean) or p_clean.startswith(perm):
            if is_negative:
                result = False
            else:
                result = True
                
    return result