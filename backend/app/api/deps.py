from fastapi import Depends

from app.security import current_session

authenticated = [Depends(current_session)]
